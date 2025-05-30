import _asdl.loma as loma_ir
import autodiff
import ir
import irmutator

ir.generate_asdl_file()


def forward_diff(
    diff_func_id: str,
    structs: dict[str, loma_ir.Struct],
    funcs: dict[str, loma_ir.func],
    diff_structs: dict[str, loma_ir.Struct],
    func: loma_ir.FunctionDef,
    func_to_fwd: dict[str, str],
) -> loma_ir.FunctionDef:
    """Given a primal loma function func, apply forward differentiation
    and return a function that computes the total derivative of func.
    """

    class FwdDiffMutator(irmutator.IRMutator):
        def mutate_function_def(self, node):
            new_func_args = [
                loma_ir.Arg(
                    arg.id, autodiff.type_to_diff_type(
                        diff_structs, arg.t), arg.i
                )
                for arg in node.args
            ]
            new_body = [self.mutate_stmt(stmt) for stmt in node.body]
            new_body = irmutator.flatten(new_body)
            return loma_ir.FunctionDef(
                diff_func_id,
                new_func_args,
                new_body,
                node.is_simd,
                autodiff.type_to_diff_type(diff_structs, node.ret_type),
                node.lineno,
            )

        def mutate_return(self, node):
            val, dval = self.mutate_expr(node.val)
            if isinstance(node.val.t, loma_ir.Int):
                return loma_ir.Return(val, lineno=node.lineno)
            elif isinstance(node.val.t, loma_ir.Float):
                assembled_result = loma_ir.Call(
                    "make__dfloat",
                    (val, dval),
                    t=autodiff.type_to_diff_type(diff_structs, node.val.t)
                )
                return loma_ir.Return(assembled_result, lineno=node.lineno)
            elif isinstance(node.val.t, loma_ir.Struct):
                return loma_ir.Return(val, lineno=node.lineno)
            else:
                return loma_ir.Return(val, lineno=node.lineno)

        def mutate_declare(self, node):
            new_val = None
            new_type = autodiff.type_to_diff_type(diff_structs, node.t)
            if node.val:
                val, dval = self.mutate_expr(node.val)
                if isinstance(node.t, loma_ir.Int) or isinstance(node.t, loma_ir.Struct):
                    new_val = val
                else:
                    new_val = loma_ir.Call(
                        "make__dfloat", (val, dval), t=new_type)
            return loma_ir.Declare(node.target, new_type, new_val, node.lineno)

        def mutate_assign(self, node):
            rhs_val, rhs_dval = self.mutate_expr(node.val)
            new_rhs = None
            lhs_diff_type = autodiff.type_to_diff_type(
                diff_structs, node.target.t)

            if isinstance(node.target.t, loma_ir.Int) or isinstance(node.target.t, loma_ir.Struct):
                new_rhs = rhs_val
            elif isinstance(node.target.t, loma_ir.Float):
                new_rhs = loma_ir.Call(
                    "make__dfloat", (rhs_val, rhs_dval), t=lhs_diff_type)
            else:
                new_rhs = rhs_val
            new_lhs = self.mutate_expr_lhs(node.target)
            return loma_ir.Assign(new_lhs, new_rhs, lineno=node.lineno)

        def mutate_expr_lhs(self, node_target):
            if isinstance(node_target, loma_ir.Var):
                return node_target
            elif isinstance(node_target, loma_ir.ArrayAccess):
                index_val, _ = self.mutate_expr(node_target.index)
                if not isinstance(node_target.index.t, loma_ir.Int):
                    if not (isinstance(index_val, loma_ir.Call) and index_val.id == "float2int"):
                        # Should be float2int for index
                        index_val = loma_ir.Call(
                            "int2float", (index_val,), t=loma_ir.Int())
                mutated_array = self.mutate_expr_lhs(node_target.array)
                element_diff_type = autodiff.type_to_diff_type(
                    diff_structs, node_target.t)
                return loma_ir.ArrayAccess(
                    array=mutated_array, index=index_val,
                    lineno=node_target.lineno, t=element_diff_type
                )
            elif isinstance(node_target, loma_ir.StructAccess):
                mutated_struct = self.mutate_expr_lhs(node_target.struct)
                member_diff_type = autodiff.type_to_diff_type(
                    diff_structs, node_target.t)
                return loma_ir.StructAccess(
                    struct=mutated_struct, member_id=node_target.member_id,
                    lineno=node_target.lineno, t=member_diff_type
                )
            else:
                primal_part, _ = self.mutate_expr(node_target)
                return primal_part

        def mutate_ifelse(self, node):
            cond_val, _ = self.mutate_expr(node.cond)
            new_then_stmts = [self.mutate_stmt(
                stmt) for stmt in node.then_stmts]
            new_then_stmts = irmutator.flatten(new_then_stmts)
            new_else_stmts = [self.mutate_stmt(
                stmt) for stmt in node.else_stmts]
            new_else_stmts = irmutator.flatten(new_else_stmts)
            return loma_ir.IfElse(cond_val, new_then_stmts, new_else_stmts, lineno=node.lineno)

        def mutate_while(self, node: loma_ir.While):
            # Mutate the condition (only primal needed for control flow)
            cond_val, _ = self.mutate_expr(node.cond)

            # Mutate the statements within the loop body
            new_body = [self.mutate_stmt(stmt) for stmt in node.body]
            new_body = irmutator.flatten(new_body)

            # Construct the new While loop with mutated condition and body
            return loma_ir.While(
                cond_val,
                node.max_iter,  # max_iter remains the same
                new_body,
                lineno=node.lineno
            )

        def mutate_const_float(self, node):
            return loma_ir.ConstFloat(node.val), loma_ir.ConstFloat(0.0)

        def mutate_const_int(self, node):
            return loma_ir.ConstInt(node.val), loma_ir.ConstFloat(0.0)

        def mutate_var(self, node):
            if isinstance(node.t, loma_ir.Int):
                return node, loma_ir.ConstFloat(0.0)
            elif isinstance(node.t, loma_ir.Float):
                val = loma_ir.StructAccess(node, "val", t=loma_ir.Float())
                dval = loma_ir.StructAccess(node, "dval", t=loma_ir.Float())
                return val, dval
            elif isinstance(node.t, loma_ir.Struct):
                # Placeholder, may need member-wise handling
                return node, loma_ir.ConstFloat(0.0)
            # Fallback for other types if any (e.g. Array - though access is handled separately)
            return node, loma_ir.ConstFloat(0.0)

        def mutate_array_access(self, node):
            original_array_expr = node.array
            original_index_expr = node.index
            index_val, _ = self.mutate_expr(original_index_expr)
            if not isinstance(original_index_expr.t, loma_ir.Int):
                # Ensure it's an int
                if not (isinstance(index_val, loma_ir.Call) and index_val.id == "float2int"):
                    index_val = loma_ir.Call(
                        "float2int", (index_val,), t=loma_ir.Int())

            mutated_array_expr, _ = self.mutate_expr(original_array_expr)
            array_element_diff_type = autodiff.type_to_diff_type(
                diff_structs, node.t)
            array_element_access = loma_ir.ArrayAccess(
                array=mutated_array_expr, index=index_val,
                lineno=node.lineno, t=array_element_diff_type
            )
            if isinstance(node.t, loma_ir.Float):
                val = loma_ir.StructAccess(
                    array_element_access, "val", t=loma_ir.Float())
                dval = loma_ir.StructAccess(
                    array_element_access, "dval", t=loma_ir.Float())
                return val, dval
            elif isinstance(node.t, loma_ir.Int) or isinstance(node.t, loma_ir.Struct):
                return array_element_access, loma_ir.ConstFloat(0.0)
            else:
                raise NotImplementedError(
                    f"Array access for element type {node.t} not implemented.")

        def mutate_struct_access(self, node):
            original_struct_expr = node.struct
            mutated_struct_expr, _ = self.mutate_expr(original_struct_expr)
            member_diff_type = autodiff.type_to_diff_type(diff_structs, node.t)
            member_access_expr = loma_ir.StructAccess(
                struct=mutated_struct_expr, member_id=node.member_id,
                lineno=node.lineno, t=member_diff_type
            )
            if isinstance(node.t, loma_ir.Float):
                val = loma_ir.StructAccess(
                    member_access_expr, "val", t=loma_ir.Float())
                dval = loma_ir.StructAccess(
                    member_access_expr, "dval", t=loma_ir.Float())
                return val, dval
            elif isinstance(node.t, loma_ir.Int) or isinstance(node.t, loma_ir.Struct):
                return member_access_expr, loma_ir.ConstFloat(0.0)
            else:
                raise NotImplementedError(
                    f"Struct access for member type {node.t} not implemented.")

        def _create_comparison_op(self, node, op_constructor):
            left_val, _ = self.mutate_expr(node.left)
            right_val, _ = self.mutate_expr(node.right)
            primal_op_result = loma_ir.BinaryOp(
                op_constructor(), left_val, right_val,
                lineno=node.lineno, t=loma_ir.Int()
            )
            dval_op_result = loma_ir.ConstFloat(0.0)
            return primal_op_result, dval_op_result

        def mutate_less(self, node): return self._create_comparison_op(
            node, loma_ir.Less)

        def mutate_less_equal(self, node): return self._create_comparison_op(
            node, loma_ir.LessEqual)

        def mutate_greater(self, node): return self._create_comparison_op(
            node, loma_ir.Greater)

        def mutate_greater_equal(self, node): return self._create_comparison_op(
            node, loma_ir.GreaterEqual)

        def mutate_equal(self, node): return self._create_comparison_op(
            node, loma_ir.Equal)

        def mutate_and(self, node): return self._create_comparison_op(
            node, loma_ir.And)  # Simplified, assumes inputs are already bool-like (Int)

        def mutate_or(self, node): return self._create_comparison_op(
            node, loma_ir.Or)   # Simplified

        def mutate_add(self, node):
            left_val, left_dval = self.mutate_expr(node.left)
            right_val, right_dval = self.mutate_expr(node.right)
            is_int_op = isinstance(node.left.t, loma_ir.Int) and isinstance(
                node.right.t, loma_ir.Int)
            primal_res_type = loma_ir.Int() if is_int_op else loma_ir.Float()
            ln = node.lineno
            if not is_int_op:
                if isinstance(node.left.t, loma_ir.Int):
                    left_val = loma_ir.Call(
                        "int2float", (left_val,), t=loma_ir.Float(), lineno=ln)
                if isinstance(node.right.t, loma_ir.Int):
                    right_val = loma_ir.Call(
                        "int2float", (right_val,), t=loma_ir.Float(), lineno=ln)
            result_val = loma_ir.BinaryOp(
                loma_ir.Add(), left_val, right_val, lineno=ln, t=primal_res_type)
            result_dval = loma_ir.ConstFloat(0.0) if is_int_op else loma_ir.BinaryOp(
                loma_ir.Add(), left_dval, right_dval, lineno=ln, t=loma_ir.Float())
            return result_val, result_dval

        def mutate_sub(self, node):
            left_val, left_dval = self.mutate_expr(node.left)
            right_val, right_dval = self.mutate_expr(node.right)
            is_int_op = isinstance(node.left.t, loma_ir.Int) and isinstance(
                node.right.t, loma_ir.Int)
            primal_res_type = loma_ir.Int() if is_int_op else loma_ir.Float()
            ln = node.lineno
            if not is_int_op:
                if isinstance(node.left.t, loma_ir.Int):
                    left_val = loma_ir.Call(
                        "int2float", (left_val,), t=loma_ir.Float(), lineno=ln)
                if isinstance(node.right.t, loma_ir.Int):
                    right_val = loma_ir.Call(
                        "int2float", (right_val,), t=loma_ir.Float(), lineno=ln)
            result_val = loma_ir.BinaryOp(
                loma_ir.Sub(), left_val, right_val, lineno=ln, t=primal_res_type)
            result_dval = loma_ir.ConstFloat(0.0) if is_int_op else loma_ir.BinaryOp(
                loma_ir.Sub(), left_dval, right_dval, lineno=ln, t=loma_ir.Float())
            return result_val, result_dval

        def mutate_mul(self, node):
            left_val, left_dval = self.mutate_expr(node.left)
            right_val, right_dval = self.mutate_expr(node.right)
            is_int_op = isinstance(node.left.t, loma_ir.Int) and isinstance(
                node.right.t, loma_ir.Int)
            primal_res_type = loma_ir.Int() if is_int_op else loma_ir.Float()
            ln = node.lineno
            if not is_int_op:
                if isinstance(node.left.t, loma_ir.Int):
                    left_val = loma_ir.Call(
                        "int2float", (left_val,), t=loma_ir.Float(), lineno=ln)
                if isinstance(node.right.t, loma_ir.Int):
                    right_val = loma_ir.Call(
                        "int2float", (right_val,), t=loma_ir.Float(), lineno=ln)
            result_val = loma_ir.BinaryOp(
                loma_ir.Mul(), left_val, right_val, lineno=ln, t=primal_res_type)
            if is_int_op:
                result_dval = loma_ir.ConstFloat(0.0)
            else:
                term1_dval = loma_ir.BinaryOp(
                    loma_ir.Mul(), left_dval, right_val, lineno=ln, t=loma_ir.Float())
                term2_dval = loma_ir.BinaryOp(
                    loma_ir.Mul(), left_val, right_dval, lineno=ln, t=loma_ir.Float())
                result_dval = loma_ir.BinaryOp(
                    loma_ir.Add(), term1_dval, term2_dval, lineno=ln, t=loma_ir.Float())
            return result_val, result_dval

        def mutate_div(self, node):
            left_val, left_dval = self.mutate_expr(node.left)
            right_val, right_dval = self.mutate_expr(node.right)
            is_int_op = isinstance(node.left.t, loma_ir.Int) and isinstance(
                node.right.t, loma_ir.Int)
            primal_res_type = loma_ir.Int() if is_int_op else loma_ir.Float()
            ln = node.lineno
            if not is_int_op:
                if isinstance(node.left.t, loma_ir.Int):
                    left_val = loma_ir.Call(
                        "int2float", (left_val,), t=loma_ir.Float(), lineno=ln)
                if isinstance(node.right.t, loma_ir.Int):
                    right_val = loma_ir.Call(
                        "int2float", (right_val,), t=loma_ir.Float(), lineno=ln)
            result_val = loma_ir.BinaryOp(
                loma_ir.Div(), left_val, right_val, lineno=ln, t=primal_res_type)
            if is_int_op:
                result_dval = loma_ir.ConstFloat(0.0)
            else:
                num_t1 = loma_ir.BinaryOp(
                    loma_ir.Mul(), left_dval, right_val, lineno=ln, t=loma_ir.Float())
                num_t2 = loma_ir.BinaryOp(
                    loma_ir.Mul(), left_val, right_dval, lineno=ln, t=loma_ir.Float())
                num_dval = loma_ir.BinaryOp(
                    loma_ir.Sub(), num_t1, num_t2, lineno=ln, t=loma_ir.Float())
                den_dval = loma_ir.BinaryOp(
                    loma_ir.Mul(), right_val, right_val, lineno=ln, t=loma_ir.Float())
                result_dval = loma_ir.BinaryOp(
                    loma_ir.Div(), num_dval, den_dval, lineno=ln, t=loma_ir.Float())
            return result_val, result_dval

        def mutate_call(self, node):
            func_id = node.id
            lineno = node.lineno
            original_return_type = node.t
            match func_id:
                case "sin":
                    val, dval = self.mutate_expr(node.args[0])
                    return self.mutate_sin(val, dval, lineno)
                case "cos":
                    val, dval = self.mutate_expr(node.args[0])
                    return self.mutate_cos(val, dval, lineno)
                case "sqrt":
                    val, dval = self.mutate_expr(node.args[0])
                    return self.mutate_sqrt(val, dval, lineno)
                case "pow":
                    x_val, x_dval = self.mutate_expr(node.args[0])
                    y_val, y_dval = self.mutate_expr(node.args[1])
                    return self.mutate_pow(x_val, y_val, x_dval, y_dval, lineno)
                case "exp":
                    val, dval = self.mutate_expr(node.args[0])
                    return self.mutate_exp(val, dval, lineno)
                case "log":
                    val, dval = self.mutate_expr(node.args[0])
                    return self.mutate_log(val, dval, lineno)
                case "int2float":
                    val, _ = self.mutate_expr(node.args[0])
                    return loma_ir.Call("int2float", (val,), t=loma_ir.Float(), lineno=lineno), loma_ir.ConstFloat(0.0)
                case "float2int":
                    val, _ = self.mutate_expr(node.args[0])
                    return loma_ir.Call("float2int", [val], t=loma_ir.Int(), lineno=lineno), loma_ir.ConstFloat(0.0)
                case _:
                    if node.id in func_to_fwd:
                        diff_func_name = func_to_fwd[node.id]
                        mutated_args = []
                        original_func_def = funcs.get(node.id)
                        if not original_func_def or not isinstance(original_func_def, loma_ir.FunctionDef):
                            raise Exception(
                                f"Original function definition for {node.id} not found or not a FunctionDef.")
                        for arg_idx, arg_expr in enumerate(node.args):
                            mutated_arg_val, mutated_arg_dval = self.mutate_expr(
                                arg_expr)
                            original_arg = original_func_def.args[arg_idx]
                            if isinstance(original_arg.i, loma_ir.Out):
                                mutated_args.append(
                                    self.mutate_expr_lhs(arg_expr))
                            elif isinstance(original_arg.t, loma_ir.Int):
                                mutated_args.append(mutated_arg_val)
                            elif isinstance(original_arg.t, loma_ir.Float):
                                mutated_args.append(loma_ir.Call("make__dfloat", (mutated_arg_val, mutated_arg_dval), t=autodiff.type_to_diff_type(
                                    diff_structs, original_arg.t), lineno=lineno))
                            elif isinstance(original_arg.t, loma_ir.Struct):
                                mutated_args.append(mutated_arg_val)
                            else:
                                mutated_args.append(mutated_arg_val)
                        return_diff_type = autodiff.type_to_diff_type(
                            diff_structs, original_return_type)
                        call_expr_d_type = loma_ir.Call(diff_func_name, tuple(
                            mutated_args), t=return_diff_type, lineno=lineno)
                        if isinstance(original_return_type, loma_ir.Float):
                            ret_val_access = loma_ir.StructAccess(
                                call_expr_d_type, "val", t=loma_ir.Float(), lineno=lineno)
                            ret_dval_access = loma_ir.StructAccess(
                                call_expr_d_type, "dval", t=loma_ir.Float(), lineno=lineno)
                            return ret_val_access, ret_dval_access
                        elif isinstance(original_return_type, loma_ir.Int) or isinstance(original_return_type, loma_ir.Struct):
                            return call_expr_d_type, loma_ir.ConstFloat(0.0)
                        elif original_return_type is None:
                            print(
                                f"Warning: mutate_call called for void function {node.id}")
                            return None, None
                        else:
                            raise NotImplementedError(
                                f"Return type {original_return_type} from user function {node.id} not handled in mutate_call.")
                    else:
                        mutated_args_primal = []
                        for arg_expr in node.args:
                            arg_val, _ = self.mutate_expr(arg_expr)
                            mutated_args_primal.append(arg_val)
                        primal_call = loma_ir.Call(node.id, tuple(
                            mutated_args_primal), t=original_return_type, lineno=lineno)
                        return primal_call, loma_ir.ConstFloat(0.0)

        def mutate_call_stmt(self, node):
            func_id = node.call.id
            lineno = node.lineno
            if func_id in func_to_fwd:
                diff_func_name = func_to_fwd[func_id]
                mutated_args = []
                original_func_def = funcs.get(func_id)
                if not original_func_def or not isinstance(original_func_def, loma_ir.FunctionDef):
                    raise Exception(
                        f"Original function definition for {func_id} not found or not a FunctionDef.")
                for arg_idx, arg_expr in enumerate(node.call.args):
                    mutated_arg_val, mutated_arg_dval = self.mutate_expr(
                        arg_expr)
                    original_arg = original_func_def.args[arg_idx]
                    if isinstance(original_arg.i, loma_ir.Out):
                        mutated_args.append(self.mutate_expr_lhs(arg_expr))
                    elif isinstance(original_arg.t, loma_ir.Int):
                        mutated_args.append(mutated_arg_val)
                    elif isinstance(original_arg.t, loma_ir.Float):
                        mutated_args.append(loma_ir.Call("make__dfloat", (mutated_arg_val, mutated_arg_dval), t=autodiff.type_to_diff_type(
                            diff_structs, original_arg.t), lineno=lineno))
                    elif isinstance(original_arg.t, loma_ir.Struct):
                        mutated_args.append(mutated_arg_val)
                    else:
                        mutated_args.append(mutated_arg_val)
                diff_call_expr = loma_ir.Call(diff_func_name, tuple(
                    mutated_args), t=None, lineno=lineno)
                return loma_ir.CallStmt(diff_call_expr, lineno=lineno)
            else:
                mutated_args_primal = []
                for arg_expr in node.call.args:
                    arg_val, _ = self.mutate_expr(arg_expr)
                    mutated_args_primal.append(arg_val)
                primal_call_expr = loma_ir.Call(func_id, tuple(
                    mutated_args_primal), t=None, lineno=lineno)
                return loma_ir.CallStmt(primal_call_expr, lineno=lineno)

        def mutate_sin(self, val, dval, lineno):
            return (loma_ir.Call("sin", (val,), t=loma_ir.Float(), lineno=lineno),
                    loma_ir.BinaryOp(loma_ir.Mul(), loma_ir.Call("cos", (val,), t=loma_ir.Float(), lineno=lineno), dval, t=loma_ir.Float(), lineno=lineno))

        def mutate_cos(self, val, dval, lineno):
            return (loma_ir.Call("cos", (val,), t=loma_ir.Float(), lineno=lineno),
                    loma_ir.BinaryOp(loma_ir.Mul(), loma_ir.BinaryOp(loma_ir.Mul(), loma_ir.ConstFloat(-1.0), dval, t=loma_ir.Float(), lineno=lineno), loma_ir.Call("sin", (val,), t=loma_ir.Float(), lineno=lineno), t=loma_ir.Float(), lineno=lineno))

        def mutate_sqrt(self, val, dval, lineno):
            return (loma_ir.Call("sqrt", (val,), t=loma_ir.Float(), lineno=lineno),
                    loma_ir.BinaryOp(loma_ir.Div(), dval, loma_ir.BinaryOp(loma_ir.Mul(), loma_ir.ConstFloat(2.0), loma_ir.Call("sqrt", (val,), t=loma_ir.Float(), lineno=lineno), t=loma_ir.Float(), lineno=lineno), t=loma_ir.Float(), lineno=lineno))

        def mutate_pow(self, x_val, y_val, x_dval, y_dval, lineno):
            primal_call = loma_ir.Call(
                "pow", (x_val, y_val), t=loma_ir.Float(), lineno=lineno)
            y_minus_1 = loma_ir.BinaryOp(loma_ir.Sub(), y_val, loma_ir.ConstFloat(
                1.0), t=loma_ir.Float(), lineno=lineno)
            pow_x_y_minus_1 = loma_ir.Call(
                "pow", (x_val, y_minus_1), t=loma_ir.Float(), lineno=lineno)
            term1_factor1 = loma_ir.BinaryOp(
                loma_ir.Mul(), y_val, pow_x_y_minus_1, t=loma_ir.Float(), lineno=lineno)
            term1 = loma_ir.BinaryOp(
                loma_ir.Mul(), term1_factor1, x_dval, t=loma_ir.Float(), lineno=lineno)
            log_x = loma_ir.Call(
                "log", (x_val,), t=loma_ir.Float(), lineno=lineno)
            term2_factor1 = loma_ir.BinaryOp(
                loma_ir.Mul(), primal_call, log_x, t=loma_ir.Float(), lineno=lineno)
            term2 = loma_ir.BinaryOp(
                loma_ir.Mul(), term2_factor1, y_dval, t=loma_ir.Float(), lineno=lineno)
            total_dval = loma_ir.BinaryOp(
                loma_ir.Add(), term1, term2, t=loma_ir.Float(), lineno=lineno)
            return primal_call, total_dval

        def mutate_exp(self, val, dval, lineno):
            return (loma_ir.Call("exp", (val,), t=loma_ir.Float(), lineno=lineno),
                    loma_ir.BinaryOp(loma_ir.Mul(), loma_ir.Call("exp", (val,), t=loma_ir.Float(), lineno=lineno), dval, t=loma_ir.Float(), lineno=lineno))

        def mutate_log(self, val, dval, lineno):
            return (loma_ir.Call("log", (val,), t=loma_ir.Float(), lineno=lineno),
                    loma_ir.BinaryOp(loma_ir.Div(), dval, val, t=loma_ir.Float(), lineno=lineno))

    return FwdDiffMutator().mutate_function_def(func)
