import random
import string

import _asdl.loma as loma_ir
import ir
import irmutator

ir.generate_asdl_file()


def random_id_generator(size=3, chars=string.ascii_lowercase + string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def reverse_diff(diff_func_id: str,
                 structs: dict[str, loma_ir.Struct],
                 funcs: dict[str, loma_ir.func],
                 diff_structs: dict[str, loma_ir.Struct],
                 func: loma_ir.FunctionDef,
                 func_to_rev: dict[str, str]) -> loma_ir.FunctionDef:

    def type_to_string(t):
        match t:
            case loma_ir.Int(): return 'int'
            case loma_ir.Float(): return 'float'
            case loma_ir.Array(t_inner, size):
                size_str = f"_{size}" if size is not None else ""
                return f'array_{type_to_string(t_inner)}{size_str}'
            case loma_ir.Struct(id_s, _, _): return id_s
            case None: return 'void'
            case _: return 'unknown_type'

    def get_base_id(expr_node):
        curr = expr_node
        while True:
            if isinstance(curr, loma_ir.Var):
                return curr.id
            elif isinstance(curr, loma_ir.ArrayAccess):
                curr = curr.array
            elif isinstance(curr, loma_ir.StructAccess):
                curr = curr.struct
            else:
                return None

    def var_to_differential(expr, var_to_dvar_map):
        match expr:
            case loma_ir.Var(id_v, _, t_v):
                if id_v not in var_to_dvar_map:
                    if isinstance(t_v, loma_ir.Int):
                        return expr
                    raise KeyError(
                        f"Differential for variable '{id_v}' (type: {type_to_string(t_v)}) not found in var_to_dvar_map. Available: {list(var_to_dvar_map.keys())}")
                return loma_ir.Var(var_to_dvar_map[id_v], t=t_v, lineno=expr.lineno)
            case loma_ir.ArrayAccess(array_aa, index_aa, _, t_aa):
                base_var_id = get_base_id(array_aa)
                if base_var_id and base_var_id in var_to_dvar_map:
                    diff_base_array = var_to_differential(
                        array_aa, var_to_dvar_map)
                    return loma_ir.ArrayAccess(diff_base_array, index_aa, t=t_aa, lineno=expr.lineno)
                return expr
            case loma_ir.StructAccess(struct_sa, member_id_sa, _, t_sa):
                base_var_id = get_base_id(struct_sa)
                if base_var_id and base_var_id in var_to_dvar_map:
                    diff_base_struct = var_to_differential(
                        struct_sa, var_to_dvar_map)
                    return loma_ir.StructAccess(diff_base_struct, member_id_sa, t=t_sa, lineno=expr.lineno)
                return expr
            case _:
                raise TypeError(f"var_to_differential unhandled: {type(expr)}")

    def assign_zero(target):
        if not hasattr(target, 't') or target.t is None:
            return []
        match target.t:
            case loma_ir.Int(): return []
            case loma_ir.Float(): return [loma_ir.Assign(target, loma_ir.ConstFloat(0.0), lineno=target.lineno)]
            case loma_ir.Struct(id_s, _, _):
                s_type_def = structs.get(id_s) or diff_structs.get(id_s)
                stmts = []
                if s_type_def and hasattr(s_type_def, 'members'):
                    for m in s_type_def.members:
                        stmts.extend(assign_zero(loma_ir.StructAccess(
                            target, m.id, t=m.t, lineno=target.lineno)))
                return stmts
            case loma_ir.Array(t_arr_inner, static_size_arr):
                stmts = []
                if static_size_arr is not None and not isinstance(t_arr_inner, loma_ir.Int):
                    for i in range(static_size_arr):
                        stmts.extend(assign_zero(loma_ir.ArrayAccess(
                            target, loma_ir.ConstInt(i), t=t_arr_inner, lineno=target.lineno)))
                return stmts
            case _: return []

    def accum_deriv(target, deriv, overwrite, is_simd_context=False):
        if not hasattr(target, 't') or target.t is None or not hasattr(deriv, 't') or deriv.t is None:
            return []
        if isinstance(target.t, loma_ir.Int):
            return []
        target_is_scalar_var_not_access = isinstance(
            target, loma_ir.Var) and not isinstance(target.t, (loma_ir.Array, loma_ir.Struct))
        match target.t:
            case loma_ir.Float():
                actual_deriv = deriv
                if isinstance(deriv.t, loma_ir.Int) and isinstance(target.t, loma_ir.Float):
                    actual_deriv = loma_ir.Call("int2float", (deriv,), t=loma_ir.Float(
                    ), lineno=getattr(deriv, 'lineno', target.lineno))
                elif not isinstance(deriv.t, loma_ir.Float) and not (overwrite and isinstance(deriv, loma_ir.ConstFloat) and deriv.val == 0.0):
                    return []
                if is_simd_context and target_is_scalar_var_not_access and not overwrite:
                    return [loma_ir.CallStmt(loma_ir.Call('atomic_add', (target, actual_deriv), t=None, lineno=target.lineno))]
                else:
                    op = loma_ir.Assign(target, actual_deriv, lineno=target.lineno) if overwrite else \
                        loma_ir.Assign(target, loma_ir.BinaryOp(loma_ir.Add(
                        ), target, actual_deriv, t=loma_ir.Float(), lineno=target.lineno), lineno=target.lineno)
                    return [op]
            case loma_ir.Struct(id_s, _, _):
                s_type_def = structs.get(id_s) or diff_structs.get(id_s)
                stmts = []
                if not s_type_def or not isinstance(deriv.t, loma_ir.Struct) or deriv.t.id != id_s:
                    return []
                if hasattr(s_type_def, 'members'):
                    for m in s_type_def.members:
                        if isinstance(m.t, loma_ir.Int):
                            continue
                        is_scalar_field = isinstance(m.t, loma_ir.Float)
                        stmts.extend(accum_deriv(loma_ir.StructAccess(target, m.id, t=m.t, lineno=target.lineno),
                                                 loma_ir.StructAccess(deriv, m.id, t=m.t, lineno=getattr(
                                                     deriv, 'lineno', target.lineno)),
                                                 overwrite, is_simd_context and is_scalar_field))
                return stmts
            case loma_ir.Array(t_arr_inner, static_size_arr):
                if isinstance(target, loma_ir.ArrayAccess) and isinstance(deriv.t, loma_ir.Float) and isinstance(t_arr_inner, loma_ir.Float):
                    op = loma_ir.Assign(target, deriv, lineno=target.lineno) if overwrite else \
                        loma_ir.Assign(target, loma_ir.BinaryOp(loma_ir.Add(
                        ), target, deriv, t=target.t, lineno=target.lineno), lineno=target.lineno)
                    return [op]
                if not isinstance(deriv.t, loma_ir.Array) or type_to_string(t_arr_inner) != type_to_string(deriv.t.t) or isinstance(t_arr_inner, loma_ir.Int):
                    pass
                stmts = []
                if static_size_arr is not None and isinstance(deriv.t, loma_ir.Array) and deriv.t.static_size == static_size_arr:
                    for i in range(static_size_arr):
                        stmts.extend(accum_deriv(loma_ir.ArrayAccess(target, loma_ir.ConstInt(i), t=t_arr_inner, lineno=target.lineno),
                                                 loma_ir.ArrayAccess(deriv, loma_ir.ConstInt(
                                                     i), t=deriv.t.t, lineno=getattr(deriv, 'lineno', target.lineno)),
                                                 overwrite, False))
                return stmts
            case _: return []

    class CallNormalizeMutator(irmutator.IRMutator):
        def mutate_function_def(self, node):
            self.tmp_count = 0
            self.tmp_declare_stmts = []
            self._declared_temp_names_in_pass = set()
            new_body = irmutator.flatten(
                [self.mutate_stmt(stmt) for stmt in node.body])
            return loma_ir.FunctionDef(node.id, node.args, self.tmp_declare_stmts + new_body, node.is_simd, node.ret_type, lineno=node.lineno)

        def mutate_return(self, node): self.tmp_assign_stmts = []; val = self.mutate_expr(
            node.val); return self.tmp_assign_stmts + [loma_ir.Return(val, lineno=node.lineno)]

        def mutate_declare(self, node): self.tmp_assign_stmts = []; val = self.mutate_expr(
            node.val) if node.val is not None else None; return self.tmp_assign_stmts + [loma_ir.Declare(node.target, node.t, val, lineno=node.lineno)]

        def mutate_assign(self, node):
            self.tmp_assign_stmts = []
            self.has_call_expr = False
            val = self.mutate_expr(node.val)
            if self.has_call_expr and isinstance(val, loma_ir.Call):
                target_type = node.target.t or getattr(val, 't', None)
                if target_type is None:
                    f_def = funcs.get(val.id)
                    target_type = f_def.ret_type if f_def else None
                if target_type is None:
                    if val.id in ['sin', 'cos', 'exp', 'log', 'sqrt', 'pow'] and isinstance(getattr(node.target, 't', None), loma_ir.Float):
                        target_type = loma_ir.Float()
                    elif val.id == 'int2float':
                        target_type = loma_ir.Float()
                    elif val.id == 'float2int':
                        target_type = loma_ir.Int()
                    elif val.id == 'thread_id':
                        target_type = loma_ir.Int()
                if target_type is None:
                    raise ValueError(
                        f"CNM Assign: Type fail '{val.id}' to '{str(node.target)}'.")
                idx = self.tmp_count
                self.tmp_count += 1
                name = f'_call_res_t_{idx}_{random_id_generator()}'
                if name not in self._declared_temp_names_in_pass:
                    self.tmp_declare_stmts.append(loma_ir.Declare(
                        name, target_type, lineno=node.lineno))
                    self._declared_temp_names_in_pass.add(name)
                tmp_v = loma_ir.Var(name, t=target_type, lineno=node.lineno)
                return self.tmp_assign_stmts + [loma_ir.Assign(tmp_v, val, lineno=node.lineno), loma_ir.Assign(node.target, tmp_v, lineno=node.lineno)]
            return self.tmp_assign_stmts + [loma_ir.Assign(node.target, val, lineno=node.lineno)]

        def mutate_call_stmt(self, node): self.tmp_assign_stmts = []; expr = self.mutate_expr(
            node.call); return self.tmp_assign_stmts + [loma_ir.CallStmt(expr, lineno=node.lineno)]

        def mutate_call(self, node):
            self.has_call_expr = True
            new_args = []
            arg_assigns = []
            orig_fdef = funcs.get(node.id)
            for i, arg_e in enumerate(node.args):
                is_out = False
                exp_t = None
                if orig_fdef and i < len(orig_fdef.args):
                    spec = orig_fdef.args[i]
                    is_out = isinstance(spec.i, loma_ir.Out)
                    exp_t = spec.t
                if not isinstance(arg_e, (loma_ir.Var, loma_ir.ArrayAccess, loma_ir.StructAccess)) and not is_out:
                    mut_arg_val = self.mutate_expr(arg_e)
                    tmp_t = getattr(mut_arg_val, 't', None) or exp_t
                    if tmp_t is None:
                        if isinstance(mut_arg_val, loma_ir.ConstFloat):
                            tmp_t = loma_ir.Float()
                        elif isinstance(mut_arg_val, loma_ir.ConstInt):
                            tmp_t = loma_ir.Int()
                        elif isinstance(mut_arg_val, loma_ir.Call) and mut_arg_val.id == 'thread_id':
                            tmp_t = loma_ir.Int()
                    if tmp_t is None:
                        raise ValueError(
                            f"CNM Call: Type fail for arg '{str(arg_e)}' in '{node.id}'.")
                    idx = self.tmp_count
                    self.tmp_count += 1
                    name = f'_call_arg_t_{idx}_{random_id_generator()}'
                    if name not in self._declared_temp_names_in_pass:
                        self.tmp_declare_stmts.append(
                            loma_ir.Declare(name, tmp_t, lineno=node.lineno))
                        self._declared_temp_names_in_pass.add(name)
                    tmp_v = loma_ir.Var(name, t=tmp_t, lineno=node.lineno)
                    arg_assigns.append(loma_ir.Assign(
                        tmp_v, mut_arg_val, lineno=node.lineno))
                    new_args.append(tmp_v)
                else:
                    new_args.append(self.mutate_expr(arg_e)
                                    if not is_out else arg_e)
            self.tmp_assign_stmts.extend(arg_assigns)
            ret_t = getattr(node, 't', None)
            if ret_t is None:
                if orig_fdef:
                    ret_t = orig_fdef.ret_type
                elif node.id in ['sin', 'cos', 'sqrt', 'exp', 'log', 'pow', 'int2float']:
                    ret_t = loma_ir.Float()
                elif node.id == 'float2int':
                    ret_t = loma_ir.Int()
                elif node.id == 'thread_id':
                    ret_t = loma_ir.Int()
                elif node.id == 'atomic_add':
                    ret_t = None
            return loma_ir.Call(node.id, tuple(new_args), t=ret_t, lineno=node.lineno)

    class ForwardPassMutator(irmutator.IRMutator):
        def __init__(self, output_args_ids_main_func, initial_var_to_dvar, original_func_args_full_spec, is_simd_func, primal_out_arg_names_of_original_func):
            self.output_args_ids_main_func = output_args_ids_main_func
            self.var_to_dvar = initial_var_to_dvar.copy()
            self.assigned_vars = set()
            self.cache_vars_list = {}
            self.type_cache_size = {}
            self.type_to_stack_and_ptr_names = {}
            self.current_var_types = {
                a.id: a.t for a in original_func_args_full_spec}
            self.loop_level = 0
            self.current_loop_counter_name_stack = []
            self.all_declared_loop_counters = set()
            self.loop_iter_stack_names = {}
            self.loop_max_iters = {}
            self.func_level_loop_var_declarations = []
            self.is_simd_func = is_simd_func
            self.primal_out_arg_names_of_original_func = primal_out_arg_names_of_original_func
            self.original_func_args_full_spec = original_func_args_full_spec
            self.ordered_primary_loop_counters = []

        def _get_cache_size_increment(self):
            if self.loop_level == 0:
                return 1
            increment = 1
            for l_idx in range(self.loop_level):
                loop_counter_name = self.current_loop_counter_name_stack[l_idx] if l_idx < len(
                    self.current_loop_counter_name_stack) else None
                max_iter_for_level = self.loop_max_iters.get(
                    loop_counter_name, 10)
                increment *= max_iter_for_level
            return increment

        def mutate_function_def(self, node):
            self.assigned_vars = set()
            self.current_var_types = {}
            for arg in node.args:
                if isinstance(arg.i, loma_ir.In):
                    self.assigned_vars.add(arg.id)
                self.current_var_types[arg.id] = arg.t
            for arg_name in self.primal_out_arg_names_of_original_func:
                self.assigned_vars.add(arg_name)

            self.loop_level = 0
            self.current_loop_counter_name_stack = []
            self.all_declared_loop_counters = set()
            self.loop_iter_stack_names = {}
            self.loop_max_iters = {}
            self.func_level_loop_var_declarations = []
            self.ordered_primary_loop_counters = []
            new_body = irmutator.flatten(
                [self.mutate_stmt(s) for s in node.body])

            final_loop_decls = []
            seen_loop_decl_names = set()
            for decl in self.func_level_loop_var_declarations:
                if decl.target not in seen_loop_decl_names:
                    final_loop_decls.append(decl)
                    seen_loop_decl_names.add(decl.target)
            self.func_level_loop_var_declarations = final_loop_decls

            return loma_ir.FunctionDef(node.id, node.args, new_body, node.is_simd, node.ret_type, lineno=node.lineno)

        def mutate_return(self, node): self.mutate_expr(node.val); return []

        def mutate_declare(self, node: loma_ir.Declare) -> list[loma_ir.stmt]:
            if node.target in self.all_declared_loop_counters:
                return []

            self.current_var_types[node.target] = node.t
            val = self.mutate_expr(node.val) if node.val else None
            if node.target in self.output_args_ids_main_func or val is not None:
                self.assigned_vars.add(node.target)
            elif isinstance(node.t, loma_ir.Float) and val is None:
                val = loma_ir.ConstFloat(0.0)
                self.assigned_vars.add(node.target)
            decl = loma_ir.Declare(node.target, node.t,
                                   val, lineno=node.lineno)

            is_arg_of_current_func = node.target in {
                arg.id for arg in self.original_func_args_full_spec}
            is_primal_out_overall = node.target in self.primal_out_arg_names_of_original_func

            if not isinstance(node.t, loma_ir.Int) and not is_arg_of_current_func and not is_primal_out_overall:
                d_id = self.var_to_dvar.get(node.target)
                if not d_id:
                    d_id = '_d_local_'+node.target+'_'+random_id_generator()
                    self.var_to_dvar[node.target] = d_id
                d_val = loma_ir.ConstFloat(0.0) if isinstance(
                    node.t, loma_ir.Float) else None
                d_var_type = node.t
                if isinstance(node.t, loma_ir.Array) and node.t.static_size is None:
                    d_var_type = loma_ir.Array(node.t.t, None)
                return [decl, loma_ir.Declare(d_id, d_var_type, d_val, lineno=node.lineno)]
            return [decl]

        def mutate_var(self, n: loma_ir.Var) -> loma_ir.Var: return loma_ir.Var(
            n.id, t=self.current_var_types.get(n.id, n.t), lineno=n.lineno)

        def mutate_assign(self, node: loma_ir.Assign) -> list[loma_ir.stmt]:
            base_id = get_base_id(node.target)
            if base_id and base_id in self.primal_out_arg_names_of_original_func:
                return []

            lhs = self.mutate_expr(node.target)
            rhs = self.mutate_expr(node.val)
            assign = loma_ir.Assign(lhs, rhs, lineno=node.lineno)
            lhs_t = lhs.t
            cache_s = []

            current_func_in_param_names = {arg.id for arg_p_spec in self.original_func_args_full_spec for arg in (
                [arg_p_spec] if not isinstance(arg_p_spec, tuple) else arg_p_spec) if isinstance(arg.i, loma_ir.In)}
            is_local_var_for_caching = base_id and \
                base_id not in self.primal_out_arg_names_of_original_func and \
                base_id not in current_func_in_param_names

            # MODIFIED LINE: removed "and not isinstance(lhs_t, loma_ir.Int)"
            if is_local_var_for_caching and lhs_t:
                is_ow = base_id in self.assigned_vars
                if is_ow:  # Only cache if it's an overwrite of a variable already seen
                    # This should handle 'int' correctly
                    t_s = type_to_string(lhs_t)
                    if t_s not in self.type_to_stack_and_ptr_names:
                        r_id = random_id_generator()
                        self.type_to_stack_and_ptr_names[t_s] = (
                            f'_t_{t_s}_{r_id}', f'_stack_ptr_{t_s}_{r_id}')
                        self.type_cache_size[t_s] = 0
                    s_n, s_p_n = self.type_to_stack_and_ptr_names[t_s]
                    s_p_v = loma_ir.Var(
                        s_p_n, t=loma_ir.Int(), lineno=node.lineno)

                    # Determine cache size increment based on loop depth
                    current_cache_size_increment = self._get_cache_size_increment()

                    # Update the total cache size for this type
                    # Ensure type_cache_size[t_s] is based on actual usage if dynamic
                    # For now, assuming _get_cache_size_increment works correctly for all scenarios
                    self.type_cache_size[t_s] += current_cache_size_increment

                    # The array access needs the current total size known at declaration time.
                    # This part is tricky; the stack array declaration needs a fixed max size.
                    # The ForwardPassMutator collects all type_cache_size, and these are used
                    # to declare the stacks at the beginning of RevDiffMutator.
                    # For the ArrayAccess node itself, its type should be the element type.
                    # The s_arr_t variable below might be unused if stack_array_type is declared globally.
                    # s_arr_t = loma_ir.Array(lhs_t, self.type_cache_size[t_s]) # Example of array type

                    cache_e = loma_ir.ArrayAccess(loma_ir.Var(
                        s_n, t=loma_ir.Array(lhs_t, None)),  # Use None for dynamic size in access, actual size in declaration
                        s_p_v, t=lhs_t, lineno=node.lineno)

                    cache_s.extend([loma_ir.Assign(cache_e, lhs, lineno=node.lineno),
                                    loma_ir.Assign(s_p_v, loma_ir.BinaryOp(
                                        loma_ir.Add(), s_p_v, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=node.lineno)])
                    if t_s not in self.cache_vars_list:
                        self.cache_vars_list[t_s] = []
                    self.cache_vars_list[t_s].append((cache_e, lhs))
                    # self.type_cache_size[t_s] updated above
            if base_id:
                self.assigned_vars.add(base_id)
            return cache_s+[assign]

        def mutate_ifelse(self, node: loma_ir.IfElse):
            cond = self.mutate_expr(node.cond)
            vars_b, types_b, loop_lvl_b, loop_stack_b, loop_max_iters_b = self.assigned_vars.copy(), self.current_var_types.copy(
            ), self.loop_level, list(self.current_loop_counter_name_stack), self.loop_max_iters.copy()
            then_s = irmutator.flatten(
                [self.mutate_stmt(s) for s in node.then_stmts])
            vars_at, types_at, loop_lvl_at, loop_stack_at, loop_max_iters_at = self.assigned_vars.copy(
            ), self.current_var_types.copy(), self.loop_level, list(self.current_loop_counter_name_stack), self.loop_max_iters.copy()
            self.assigned_vars, self.current_var_types, self.loop_level, self.current_loop_counter_name_stack, self.loop_max_iters = vars_b, types_b, loop_lvl_b, loop_stack_b, loop_max_iters_b
            else_s = irmutator.flatten(
                [self.mutate_stmt(s) for s in node.else_stmts])
            self.assigned_vars.update(vars_at)
            self.current_var_types.update(types_at)
            self.loop_level, self.current_loop_counter_name_stack, self.loop_max_iters = loop_lvl_at, loop_stack_at, loop_max_iters_at
            return [loma_ir.IfElse(cond, then_s, else_s, lineno=node.lineno)]

        def mutate_while(self, node: loma_ir.While) -> list[loma_ir.stmt]:
            cond = self.mutate_expr(node.cond)
            self.loop_level += 1
            curr_lvl = self.loop_level

            l_var_n = f'_loop_var_{curr_lvl}_{random_id_generator()}'
            while l_var_n in self.all_declared_loop_counters:
                l_var_n = f'_loop_var_{curr_lvl}_{random_id_generator(size=4)}'
            self.all_declared_loop_counters.add(l_var_n)
            self.ordered_primary_loop_counters.append(l_var_n)
            self.current_loop_counter_name_stack.append(l_var_n)
            self.loop_max_iters[l_var_n] = node.max_iter if node.max_iter else 10
            self.func_level_loop_var_declarations.append(loma_ir.Declare(
                l_var_n, loma_ir.Int(), loma_ir.ConstInt(0), lineno=node.lineno))

            l_var_e = loma_ir.Var(l_var_n, t=loma_ir.Int(), lineno=node.lineno)
            inner_tmp_iter_e = None
            pre_s = []
            post_s = []
            if curr_lvl > 1:
                inner_tmp_iter_n = f'_loop_tmp_iter_{curr_lvl}_{random_id_generator()}'
                while inner_tmp_iter_n in self.all_declared_loop_counters:
                    inner_tmp_iter_n = f'_loop_tmp_iter_{curr_lvl}_{random_id_generator(size=4)}'
                self.all_declared_loop_counters.add(inner_tmp_iter_n)
                inner_tmp_iter_e = loma_ir.Var(
                    inner_tmp_iter_n, t=loma_ir.Int())
                self.func_level_loop_var_declarations.append(loma_ir.Declare(
                    inner_tmp_iter_n, loma_ir.Int(), lineno=node.lineno))
                pre_s.append(loma_ir.Assign(inner_tmp_iter_e,
                             loma_ir.ConstInt(0), lineno=node.lineno))

                if curr_lvl not in self.loop_iter_stack_names:
                    iter_s_n_base = f'_loop_iter_stack_{curr_lvl}'
                    iter_s_p_n_base = f'_loop_iter_stack_ptr_{curr_lvl}'
                    iter_s_n = iter_s_n_base + "_" + random_id_generator()
                    iter_s_p_n = iter_s_p_n_base + "_" + random_id_generator()
                    while iter_s_n in self.all_declared_loop_counters or iter_s_p_n in self.all_declared_loop_counters:
                        iter_s_n = iter_s_n_base + "_" + \
                            random_id_generator(size=4)
                        iter_s_p_n = iter_s_p_n_base + \
                            "_" + random_id_generator(size=4)
                    self.all_declared_loop_counters.add(iter_s_n)
                    self.all_declared_loop_counters.add(iter_s_p_n)

                    self.loop_iter_stack_names[curr_lvl] = (
                        iter_s_n, iter_s_p_n)
                    iter_stack_actual_size = 1
                    for i_loop_stack in range(curr_lvl - 1):
                        parent_loop_c = self.current_loop_counter_name_stack[i_loop_stack]
                        iter_stack_actual_size *= self.loop_max_iters.get(
                            parent_loop_c, 10)
                    self.func_level_loop_var_declarations.extend([loma_ir.Declare(iter_s_n, loma_ir.Array(loma_ir.Int(
                    ), iter_stack_actual_size if iter_stack_actual_size > 0 else 10), lineno=node.lineno), loma_ir.Declare(iter_s_p_n, loma_ir.Int(), loma_ir.ConstInt(0), lineno=node.lineno)])

                iter_s_n, iter_s_p_n = self.loop_iter_stack_names[curr_lvl]
                iter_stack_var_size_for_access = 1
                for i_loop_stack2 in range(curr_lvl - 1):
                    parent_loop_c2 = self.current_loop_counter_name_stack[i_loop_stack2]
                    iter_stack_var_size_for_access *= self.loop_max_iters.get(
                        parent_loop_c2, 10)
                stack_v = loma_ir.Var(iter_s_n, t=loma_ir.Array(loma_ir.Int(
                ), iter_stack_var_size_for_access if iter_stack_var_size_for_access > 0 else 10))
                stack_p_v = loma_ir.Var(iter_s_p_n, t=loma_ir.Int())
                post_s.extend([loma_ir.Assign(loma_ir.ArrayAccess(stack_v, stack_p_v, t=loma_ir.Int()), inner_tmp_iter_e, lineno=node.lineno), loma_ir.Assign(
                    stack_p_v, loma_ir.BinaryOp(loma_ir.Add(), stack_p_v, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=node.lineno)])

            body_s = irmutator.flatten(
                [self.mutate_stmt(s) for s in node.body])
            final_body = list(body_s)
            if inner_tmp_iter_e:
                final_body.append(loma_ir.Assign(inner_tmp_iter_e, loma_ir.BinaryOp(loma_ir.Add(
                ), inner_tmp_iter_e, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=node.lineno))
            final_body.append(loma_ir.Assign(l_var_e, loma_ir.BinaryOp(loma_ir.Add(
            ), l_var_e, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=node.lineno))
            loop = loma_ir.While(cond, node.max_iter,
                                 final_body, lineno=node.lineno)
            self.current_loop_counter_name_stack.pop()
            self.loop_level -= 1
            return pre_s+[loop]+post_s

        def mutate_call(self, node):
            args = [self.mutate_expr(a) for a in node.args]
            fdef = funcs.get(node.id)
            ret_t = getattr(node, 't', None)
            if ret_t is None:
                if fdef:
                    ret_t = fdef.ret_type
                elif node.id in ['sin', 'cos', 'sqrt', 'exp', 'log', 'pow', 'int2float']:
                    ret_t = loma_ir.Float()
                elif node.id == 'float2int':
                    ret_t = loma_ir.Int()
                elif node.id == 'thread_id':
                    ret_t = loma_ir.Int()
                elif node.id == 'atomic_add':
                    ret_t = None
            return loma_ir.Call(node.id, tuple(args), t=ret_t, lineno=node.lineno)

        def mutate_call_stmt(self, node: loma_ir.CallStmt) -> list[loma_ir.stmt]:
            call = node.call
            orig_fdef = funcs.get(call.id)

            if call.id == 'atomic_add' and len(call.args) > 0:
                target_base_id = get_base_id(call.args[0])
                if target_base_id and target_base_id in self.primal_out_arg_names_of_original_func:
                    return []

            if orig_fdef:
                for i, arg_site_expr in enumerate(call.args):
                    if i < len(orig_fdef.args):
                        arg_spec = orig_fdef.args[i]
                        if isinstance(arg_spec.i, loma_ir.Out):
                            base_id_of_arg = get_base_id(arg_site_expr)
                            if base_id_of_arg and base_id_of_arg in self.primal_out_arg_names_of_original_func:
                                return []

            pre_cache_s = []
            mut_args = []
            for i, arg_site in enumerate(call.args):
                mut_arg_node = self.mutate_expr(arg_site)
                mut_args.append(mut_arg_node)
                if orig_fdef and i < len(orig_fdef.args):
                    orig_arg_spec = orig_fdef.args[i]
                    if isinstance(orig_arg_spec.i, loma_ir.Out):
                        base_id = get_base_id(arg_site)
                        arg_t_scope = mut_arg_node.t
                        current_func_in_param_names = {arg.id for arg_p_spec in self.original_func_args_full_spec for arg in (
                            [arg_p_spec] if not isinstance(arg_p_spec, tuple) else arg_p_spec) if isinstance(arg.i, loma_ir.In)}
                        is_local_var_used_as_out = base_id and \
                            base_id not in self.primal_out_arg_names_of_original_func and \
                            base_id not in current_func_in_param_names

                        if is_local_var_used_as_out and arg_t_scope and not isinstance(arg_t_scope, loma_ir.Int) and base_id in self.assigned_vars:
                            t_s = type_to_string(arg_t_scope)
                            if t_s not in self.type_to_stack_and_ptr_names:
                                r_id = random_id_generator()
                                self.type_to_stack_and_ptr_names[t_s] = (
                                    f'_t_{t_s}_{r_id}', f'_stack_ptr_{t_s}_{r_id}')
                                self.type_cache_size[t_s] = 0
                            s_n, s_p_n = self.type_to_stack_and_ptr_names[t_s]
                            s_p_v = loma_ir.Var(
                                s_p_n, t=loma_ir.Int(), lineno=call.lineno)
                            stack_curr_size = self.type_cache_size[t_s] + \
                                self._get_cache_size_increment()
                            s_arr_t = loma_ir.Array(
                                arg_t_scope, stack_curr_size)
                            cache_e = loma_ir.ArrayAccess(loma_ir.Var(
                                s_n, t=s_arr_t, lineno=call.lineno), s_p_v, t=arg_t_scope, lineno=call.lineno)
                            pre_cache_s.append(loma_ir.Assign(
                                cache_e, mut_arg_node, lineno=call.lineno))
                            pre_cache_s.append(loma_ir.Assign(s_p_v, loma_ir.BinaryOp(
                                loma_ir.Add(), s_p_v, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=call.lineno))
                            if t_s not in self.cache_vars_list:
                                self.cache_vars_list[t_s] = []
                            self.cache_vars_list[t_s].append(
                                (cache_e, mut_arg_node))
                            self.type_cache_size[t_s] += self._get_cache_size_increment()
                        if base_id:
                            self.assigned_vars.add(base_id)
            primal_call = loma_ir.Call(call.id, tuple(
                mut_args), t=call.t, lineno=call.lineno)
            return pre_cache_s+[loma_ir.CallStmt(primal_call, lineno=node.lineno)]

    class RevDiffMutator(irmutator.IRMutator):
        def __init__(self):
            super().__init__()
            self.adj = None
            self.loop_level_rev = 0
            self.rev_loop_iter_stack_names = {}
            self.rdm_current_loop_counter_name_stack = []
            self.adj_declaration = []
            self.adj_count = 0
            self.in_assign = False
            self.adj_accum_stmts = []
            self.current_func_is_simd = False
            self.primal_out_arg_names_local = set()
            self.current_original_func_out_names = set()
            self.is_differentiating_helper_func = False
            self.primal_ordered_primary_loop_counters = []
            self.rev_pass_fwd_ordered_loop_idx = 0

        def mutate_function_def(self, node: loma_ir.FunctionDef) -> loma_ir.FunctionDef:
            self.is_differentiating_helper_func = not (
                diff_func_id == func.id+"_rev" or diff_func_id == func.id+"_fwd_rev")

            random.seed(hash(node.id + diff_func_id))
            self.var_to_dvar = {}
            new_args_list = []
            self.output_args_ids = set()
            self.func_to_rev = func_to_rev
            self.funcs = funcs
            self.return_var_id = None
            self.current_func_is_simd = node.is_simd
            self.primal_out_arg_names_local = set()
            self.current_original_func_out_names = {
                arg.id for arg in node.args if isinstance(arg.i, loma_ir.Out)}

            existing_arg_names_in_rev_sig = set()

            for arg in node.args:
                if isinstance(arg.i, loma_ir.In):
                    new_args_list.append(arg)
                    existing_arg_names_in_rev_sig.add(arg.id)

                    dvar_id_base = '_d_inarg_'+arg.id
                    dvar_id = dvar_id_base+'_'+random_id_generator()
                    while dvar_id in existing_arg_names_in_rev_sig:
                        dvar_id = dvar_id_base+'_'+random_id_generator(size=4)

                    new_args_list.append(loma_ir.Arg(
                        dvar_id, arg.t, i=loma_ir.Out()))
                    existing_arg_names_in_rev_sig.add(dvar_id)

                    if not isinstance(arg.t, loma_ir.Int):
                        self.var_to_dvar[arg.id] = dvar_id
                elif isinstance(arg.i, loma_ir.Out):
                    self.output_args_ids.add(arg.id)
                    self.primal_out_arg_names_local.add(arg.id)
                    new_args_list.append(loma_ir.Arg(
                        arg.id, arg.t, i=loma_ir.In()))
                    existing_arg_names_in_rev_sig.add(arg.id)
                    if not isinstance(arg.t, loma_ir.Int):
                        self.var_to_dvar[arg.id] = arg.id

            if node.ret_type:
                ret_dvar_base_name = '_dreturn_'
                self.return_var_id = ret_dvar_base_name + random_id_generator()
                while self.return_var_id in existing_arg_names_in_rev_sig:
                    self.return_var_id = ret_dvar_base_name + \
                        random_id_generator(size=4)
                new_args_list.append(loma_ir.Arg(
                    self.return_var_id, node.ret_type, i=loma_ir.In()))
                existing_arg_names_in_rev_sig.add(self.return_var_id)

            new_args = tuple(new_args_list)

            cm = CallNormalizeMutator()
            cm.funcs = self.funcs
            norm_node = cm.mutate_function_def(loma_ir.FunctionDef(
                node.id, node.args, node.body, node.is_simd, node.ret_type, lineno=node.lineno))

            current_var_to_dvar_for_fm = self.var_to_dvar.copy()
            fm = ForwardPassMutator(self.output_args_ids, current_var_to_dvar_for_fm,
                                    node.args, node.is_simd, self.current_original_func_out_names)
            fm_proc_node = fm.mutate_function_def(loma_ir.FunctionDef(
                "temp_fm_"+node.id, norm_node.args, norm_node.body, norm_node.is_simd, norm_node.ret_type))

            fm_body_stmts = list(fm_proc_node.body)

            self.var_to_dvar.update(fm.var_to_dvar)
            self.cache_vars_list = fm.cache_vars_list
            self.type_cache_size = fm.type_cache_size
            self.type_to_stack_and_ptr_names = fm.type_to_stack_and_ptr_names
            self.rev_loop_iter_stack_names = fm.loop_iter_stack_names
            self.loop_max_iters = fm.loop_max_iters
            val_stack_decls = []

            self.primal_ordered_primary_loop_counters = fm.ordered_primary_loop_counters.copy()
            self.rev_pass_fwd_ordered_loop_idx = 0

            unique_fm_loop_decls = []
            seen_fm_loop_decl_names = set()
            for decl_stmt in fm.func_level_loop_var_declarations:
                if isinstance(decl_stmt, loma_ir.Declare):
                    if decl_stmt.target not in seen_fm_loop_decl_names:
                        unique_fm_loop_decls.append(decl_stmt)
                        seen_fm_loop_decl_names.add(decl_stmt.target)
                else:
                    unique_fm_loop_decls.append(decl_stmt)

            for t_s, (s_n, s_p_n) in self.type_to_stack_and_ptr_names.items():
                el_t = None
                if t_s == 'float':
                    el_t = loma_ir.Float()
                elif t_s == 'int':
                    el_t = loma_ir.Int()
                elif t_s.startswith('array_'):
                    parts = t_s.split('_', 2)
                    inner_s = parts[1]
                    sz_s = parts[2] if len(parts) > 2 else None
                    inner_t = loma_ir.Float() if inner_s == 'float' else (
                        loma_ir.Int() if inner_s == 'int' else structs.get(inner_s))
                    if inner_t:
                        el_t = loma_ir.Array(inner_t, int(
                            sz_s) if sz_s and sz_s.isdigit() else None)
                elif structs.get(t_s):
                    el_t = structs[t_s]
                if el_t and t_s in self.type_cache_size and self.type_cache_size[t_s] > 0:
                    s_size = self.type_cache_size[t_s]
                    stack_array_type = loma_ir.Array(el_t, s_size)
                    val_stack_decls.append(loma_ir.Declare(
                        s_n, stack_array_type, lineno=node.lineno))
                    val_stack_decls.append(loma_ir.Declare(
                        s_p_n, loma_ir.Int(), loma_ir.ConstInt(0), lineno=node.lineno))

            fwd_pass_stmts_combined = val_stack_decls + unique_fm_loop_decls + fm_body_stmts
            self.adj_count = 0
            self.in_assign = False
            self.adj_declaration = []
            self.loop_level_rev = 0
            self.rdm_current_loop_counter_name_stack = []
            rev_pass_stmts_intermediate = []
            for s_primal in reversed(norm_node.body):
                rev_pass_stmts_intermediate.extend(self.mutate_stmt(s_primal))
            rev_pass_stmts = irmutator.flatten(rev_pass_stmts_intermediate)
            zeroing_stmts = []

            if not self.is_differentiating_helper_func:
                for arg_spec in new_args:
                    if isinstance(arg_spec.i, loma_ir.Out) and not isinstance(arg_spec.t, loma_ir.Int):
                        zeroing_stmts.extend(assign_zero(
                            loma_ir.Var(arg_spec.id, t=arg_spec.t)))

            final_body = zeroing_stmts + fwd_pass_stmts_combined + \
                self.adj_declaration + rev_pass_stmts
            return loma_ir.FunctionDef(diff_func_id, new_args, final_body, node.is_simd, ret_type=None, lineno=node.lineno)

        def mutate_return(self, node):
            if self.return_var_id:
                orig_ret_t = func.ret_type
                if orig_ret_t:
                    self.adj = loma_ir.Var(
                        self.return_var_id, t=orig_ret_t, lineno=node.lineno)

                    if not isinstance(orig_ret_t, loma_ir.Int) and node.val and getattr(node.val, 't', None) and not isinstance(getattr(node.val, 't', None), loma_ir.Int):
                        return self.mutate_expr(node.val)
            return []

        def mutate_declare(self, node: loma_ir.Declare):
            if node.val is not None:
                if isinstance(node.t, loma_ir.Int):
                    return []
                primal_var = loma_ir.Var(
                    node.target, t=node.t, lineno=node.lineno)
                if node.target not in self.var_to_dvar:
                    return []
                dvar = var_to_differential(primal_var, self.var_to_dvar)
                tmp_adj_n = f'_adj_tmp_{self.adj_count}_{random_id_generator()}'
                self.adj_count += 1
                self.adj_declaration.append(loma_ir.Declare(
                    tmp_adj_n, node.t, lineno=node.lineno))
                tmp_adj_v = loma_ir.Var(
                    tmp_adj_n, t=node.t, lineno=node.lineno)
                stmts = []
                is_scalar_target_for_atomic = isinstance(dvar, loma_ir.Var) and not isinstance(
                    dvar.t, (loma_ir.Array, loma_ir.Struct))
                stmts.extend(accum_deriv(
                    tmp_adj_v, dvar, True, self.current_func_is_simd and is_scalar_target_for_atomic))
                stmts.extend(assign_zero(dvar))
                self.adj = tmp_adj_v
                stmts.extend(self.mutate_expr(node.val))
                return stmts
            return []

        def mutate_assign(self, node: loma_ir.Assign) -> list[loma_ir.stmt]:
            s = []
            base_id = get_base_id(node.target)
            if base_id and base_id in self.primal_out_arg_names_local:
                if node.target.t and not isinstance(node.target.t, loma_ir.Int):
                    adj_val_source_name = self.var_to_dvar.get(
                        base_id, base_id)
                    reconstructed_adj_source = node.target
                    if isinstance(node.target, loma_ir.Var) and node.target.id == base_id:
                        reconstructed_adj_source = loma_ir.Var(
                            adj_val_source_name, t=node.target.t, lineno=node.target.lineno)
                    elif isinstance(node.target, loma_ir.ArrayAccess) and get_base_id(node.target.array) == base_id:
                        base_var_for_adj = loma_ir.Var(
                            adj_val_source_name, t=node.target.array.t, lineno=node.target.array.lineno)
                        reconstructed_adj_source = loma_ir.ArrayAccess(
                            base_var_for_adj, node.target.index, t=node.target.t, lineno=node.target.lineno)
                    elif isinstance(node.target, loma_ir.StructAccess) and get_base_id(node.target.struct) == base_id:
                        base_var_for_adj = loma_ir.Var(
                            adj_val_source_name, t=node.target.struct.t, lineno=node.target.struct.lineno)
                        reconstructed_adj_source = loma_ir.StructAccess(
                            base_var_for_adj, node.target.member_id, t=node.target.t, lineno=node.target.lineno)

                    self.adj = reconstructed_adj_source
                    s.extend(self.mutate_expr(node.val))
                    self.adj = None
                return s

            lhs_t = getattr(node.target, 't', None)
            current_func_arg_names = {arg.id for arg_p in func.args for arg in (
                [arg_p] if not isinstance(arg_p, tuple) else arg_p)}

            # Condition to check if this variable *could have been* cached by ForwardPassMutator
            was_potentially_cached_local = base_id and \
                base_id not in self.primal_out_arg_names_local and \
                base_id not in current_func_arg_names  # Check it's a local variable

            if was_potentially_cached_local and lhs_t:  # MODIFIED: Allow int types
                t_s = type_to_string(lhs_t)
                if t_s in self.type_to_stack_and_ptr_names:  # Check if a stack for this type was even created
                    # Get the tracking list for this type
                    cache_l = self.cache_vars_list.get(t_s, [])

                    # Find the corresponding push operation for this specific assignment's LHS
                    # This matching logic needs to be robust. Assuming str(node.target) worked.
                    idx_pop = -1
                    # node.target is from the original statement
                    str_target_original_lhs = str(node.target)

                    for i_cl in range(len(cache_l) - 1, -1, -1):
                        # cache_l[i_cl][1] was the LHS expr used in ForwardPassMutator
                        # We need to ensure this matches the current node.target effectively
                        if str(cache_l[i_cl][1]) == str_target_original_lhs:
                            idx_pop = i_cl
                            break

                    if idx_pop != -1:  # If a corresponding cache entry was found
                        s_n, s_p_n = self.type_to_stack_and_ptr_names[t_s]
                        s_p_v = loma_ir.Var(
                            s_p_n, t=loma_ir.Int(), lineno=node.lineno)
                        s.append(loma_ir.Assign(s_p_v, loma_ir.BinaryOp(
                            loma_ir.Sub(), s_p_v, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=node.lineno))

                        # The stack array has a fixed size declared at the top of the rev func.
                        # The ArrayAccess node should use this type.
                        stack_max_size = self.type_cache_size.get(
                            t_s, 10)  # Get max size for declaration
                        stack_array_full_type = loma_ir.Array(
                            lhs_t, stack_max_size)

                        s.append(loma_ir.Assign(node.target,
                                                loma_ir.ArrayAccess(loma_ir.Var(s_n, t=stack_array_full_type),
                                                                    s_p_v, t=lhs_t), lineno=node.lineno))
                        cache_l.pop(idx_pop)  # Remove from tracking list

            self.adj = None
            if lhs_t and not isinstance(lhs_t, loma_ir.Int):
                if base_id and base_id in self.var_to_dvar and base_id not in self.primal_out_arg_names_local:
                    d_lhs = var_to_differential(node.target, self.var_to_dvar)
                    tmp_adj_n = f'_adj_tmp_{self.adj_count}_{random_id_generator()}'
                    self.adj_count += 1
                    self.adj_declaration.append(loma_ir.Declare(
                        tmp_adj_n, lhs_t, lineno=node.lineno))
                    tmp_adj_v = loma_ir.Var(
                        tmp_adj_n, t=lhs_t, lineno=node.lineno)
                    is_scalar_target_for_atomic = isinstance(d_lhs, loma_ir.Var) and not isinstance(
                        d_lhs.t, (loma_ir.Array, loma_ir.Struct))
                    s.extend(accum_deriv(tmp_adj_v, d_lhs, True,
                             self.current_func_is_simd and is_scalar_target_for_atomic))
                    s.extend(assign_zero(d_lhs))
                    self.adj = tmp_adj_v

            self.in_assign = True
            self.adj_accum_stmts = []
            rhs_s = self.mutate_expr(node.val)
            s.extend(rhs_s)
            self.in_assign = False
            s.extend(self.adj_accum_stmts)
            return s

        def mutate_ifelse(self, node: loma_ir.IfElse):
            adj_b = self.adj
            else_s = []
            if node.else_stmts:
                self.adj = adj_b
                else_s = irmutator.flatten(
                    [self.mutate_stmt(s) for s in reversed(node.else_stmts)])
            self.adj = adj_b
            then_s = irmutator.flatten(
                [self.mutate_stmt(s) for s in reversed(node.then_stmts)])
            self.adj = adj_b
            return [loma_ir.IfElse(node.cond, then_s, else_s, lineno=node.lineno)]

        def mutate_while(self, node: loma_ir.While) -> list[loma_ir.stmt]:
            self.loop_level_rev += 1
            curr_rev_lvl = self.loop_level_rev

            if self.rev_pass_fwd_ordered_loop_idx >= len(self.primal_ordered_primary_loop_counters):
                raise IndexError(
                    f"RDM While: Forward loop counter index {self.rev_pass_fwd_ordered_loop_idx} out of bounds for list of size {len(self.primal_ordered_primary_loop_counters)}.")
            curr_loop_prim_count_n = self.primal_ordered_primary_loop_counters[
                self.rev_pass_fwd_ordered_loop_idx]
            self.rev_pass_fwd_ordered_loop_idx += 1

            self.rdm_current_loop_counter_name_stack.append(
                curr_loop_prim_count_n)
            loop_ctrl_fm = loma_ir.Var(
                curr_loop_prim_count_n, t=loma_ir.Int(), lineno=node.lineno)
            pre_rev_s = []
            loop_ctrl_rev = loop_ctrl_fm
            if curr_rev_lvl > 1:
                fm_loop_id = curr_rev_lvl
                if fm_loop_id not in self.rev_loop_iter_stack_names:
                    raise KeyError(
                        f"Rev pass: Stack info for loop {fm_loop_id} missing.")
                iter_s_n, iter_s_p_n = self.rev_loop_iter_stack_names[fm_loop_id]
                iter_stack_type_size_val = 1
                for i_parent_level in range(curr_rev_lvl - 1):
                    if i_parent_level < len(self.rdm_current_loop_counter_name_stack) - 1:
                        parent_fwd_counter_name = self.rdm_current_loop_counter_name_stack[
                            i_parent_level]
                        iter_stack_type_size_val *= self.loop_max_iters.get(
                            parent_fwd_counter_name, 10)
                    else:
                        iter_stack_type_size_val *= 10

                iter_s_arr_t = loma_ir.Array(
                    loma_ir.Int(), iter_stack_type_size_val if iter_stack_type_size_val > 0 else 10)
                iter_s_v = loma_ir.Var(iter_s_n, t=iter_s_arr_t)
                iter_s_p_v = loma_ir.Var(iter_s_p_n, t=loma_ir.Int())
                pre_rev_s.append(loma_ir.Assign(iter_s_p_v, loma_ir.BinaryOp(loma_ir.Sub(
                ), iter_s_p_v, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=node.lineno))
                inner_iter_tmp_n = f'_rev_inner_iter_count_{curr_rev_lvl}_{random_id_generator()}'
                self.adj_declaration.append(loma_ir.Declare(
                    inner_iter_tmp_n, loma_ir.Int(), lineno=node.lineno))
                tmp_inner_iter_v = loma_ir.Var(
                    inner_iter_tmp_n, t=loma_ir.Int())
                pre_rev_s.append(loma_ir.Assign(tmp_inner_iter_v, loma_ir.ArrayAccess(
                    iter_s_v, iter_s_p_v, t=loma_ir.Int(), lineno=node.lineno), lineno=node.lineno))
                loop_ctrl_rev = tmp_inner_iter_v

            rev_c = loma_ir.BinaryOp(
                loma_ir.Greater(), loop_ctrl_rev, loma_ir.ConstInt(0), t=loma_ir.Int())
            adj_b_loop = self.adj
            rev_body_c = irmutator.flatten(
                [self.mutate_stmt(s) for s in reversed(node.body)])
            self.adj = adj_b_loop
            decr_loop_ctrl = loma_ir.Assign(loop_ctrl_rev, loma_ir.BinaryOp(loma_ir.Sub(
            ), loop_ctrl_rev, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=node.lineno)
            final_rev_body = rev_body_c+[decr_loop_ctrl]
            rev_while = loma_ir.While(
                rev_c, node.max_iter, final_rev_body, lineno=node.lineno)
            if len(self.rdm_current_loop_counter_name_stack) > 0:
                self.rdm_current_loop_counter_name_stack.pop()
            self.loop_level_rev -= 1
            return pre_rev_s+[rev_while]

        def mutate_call_stmt(self, node: loma_ir.CallStmt) -> list[loma_ir.stmt]:
            call = node.call
            orig_fdef = self.funcs.get(call.id)
            stmts = []

            if call.id == 'atomic_add' and len(call.args) == 2:
                primal_target_expr = call.args[0]
                primal_contrib_expr = call.args[1]
                primal_target_base_id = get_base_id(primal_target_expr)

                if primal_target_base_id and primal_target_base_id in self.primal_out_arg_names_local:
                    adj_source_name = self.var_to_dvar.get(
                        primal_target_base_id)
                    if adj_source_name:
                        adj_source_expr = loma_ir.Var(
                            adj_source_name, t=primal_target_expr.t, lineno=call.lineno)
                        adj_target_expr = var_to_differential(
                            primal_contrib_expr, self.var_to_dvar)
                        stmts.extend(accum_deriv(
                            adj_target_expr, adj_source_expr, False, is_simd_context=False))
                return stmts

            if orig_fdef and call.id in self.func_to_rev:
                rev_fn_name = self.func_to_rev[call.id]
                rev_call_args = []
                for idx, orig_arg_spec in enumerate(orig_fdef.args):
                    primal_arg_expr = call.args[idx]
                    if isinstance(orig_arg_spec.i, loma_ir.In):
                        rev_call_args.append(primal_arg_expr)
                        if not isinstance(orig_arg_spec.t, loma_ir.Int):
                            rev_call_args.append(var_to_differential(
                                primal_arg_expr, self.var_to_dvar))
                    elif isinstance(orig_arg_spec.i, loma_ir.Out):
                        if not isinstance(orig_arg_spec.t, loma_ir.Int):
                            rev_call_args.append(var_to_differential(
                                primal_arg_expr, self.var_to_dvar))
                        else:
                            rev_call_args.append(primal_arg_expr)
                if orig_fdef.ret_type and not isinstance(orig_fdef.ret_type, loma_ir.Int):
                    if self.adj:
                        rev_call_args.append(self.adj)
                    elif orig_fdef.ret_type == loma_ir.Float():
                        rev_call_args.append(loma_ir.ConstFloat(0.0))

                stmts.append(loma_ir.CallStmt(loma_ir.Call(rev_fn_name, tuple(
                    rev_call_args), t=None, lineno=call.lineno), lineno=node.lineno))

            if orig_fdef:
                for idx_post, orig_arg_spec_post in reversed(list(enumerate(orig_fdef.args))):
                    if isinstance(orig_arg_spec_post.i, loma_ir.Out):
                        arg_expr_site_post = call.args[idx_post]
                        base_id_post = get_base_id(arg_expr_site_post)
                        arg_type_post = getattr(arg_expr_site_post, 't', None)
                        current_func_arg_names = {arg.id for arg_p in func.args for arg in (
                            [arg_p] if not isinstance(arg_p, tuple) else arg_p)}
                        should_pop_post = base_id_post and \
                            base_id_post not in self.primal_out_arg_names_local and \
                            base_id_post not in current_func_arg_names and \
                            arg_type_post and not isinstance(
                                arg_type_post, loma_ir.Int)

                        if should_pop_post:
                            t_str_post = type_to_string(arg_type_post)
                            if t_str_post in self.type_to_stack_and_ptr_names:
                                cache_list_post = self.cache_vars_list.get(
                                    t_str_post, [])
                                pop_idx_post = -1
                                str_arg_expr_post = str(arg_expr_site_post)
                                for i_cl_post in range(len(cache_list_post)-1, -1, -1):
                                    if str(cache_list_post[i_cl_post][1]) == str_arg_expr_post:
                                        pop_idx_post = i_cl_post
                                        break
                                if pop_idx_post != -1:
                                    s_name_post, s_ptr_name_post = self.type_to_stack_and_ptr_names[
                                        t_str_post]
                                    s_ptr_var_post = loma_ir.Var(
                                        s_ptr_name_post, t=loma_ir.Int(), lineno=call.lineno)
                                    stmts.append(loma_ir.Assign(s_ptr_var_post, loma_ir.BinaryOp(loma_ir.Sub(
                                    ), s_ptr_var_post, loma_ir.ConstInt(1), t=loma_ir.Int()), lineno=call.lineno))
                                    stack_size_post = self.type_cache_size.get(
                                        t_str_post, 10)
                                    stack_array_type_post = loma_ir.Array(
                                        arg_type_post, stack_size_post)
                                    stmts.append(loma_ir.Assign(arg_expr_site_post, loma_ir.ArrayAccess(loma_ir.Var(
                                        s_name_post, t=stack_array_type_post), s_ptr_var_post, t=arg_type_post), lineno=call.lineno))
                                    cache_list_post.pop(pop_idx_post)
                            if base_id_post in self.var_to_dvar and not isinstance(arg_type_post, loma_ir.Int):
                                stmts.extend(assign_zero(var_to_differential(
                                    arg_expr_site_post, self.var_to_dvar)))
            return stmts

        def mutate_var(self, n: loma_ir.Var) -> list[loma_ir.stmt]:
            if n.id in self.primal_out_arg_names_local:
                return []
            nt = getattr(n, 't', None)
            if nt is None or isinstance(nt, loma_ir.Int) or self.adj is None or n.id not in self.var_to_dvar:
                return []
            td = var_to_differential(n, self.var_to_dvar)
            acc_s = accum_deriv(td, self.adj, False, self.current_func_is_simd)
            if self.in_assign:
                self.adj_accum_stmts.extend(acc_s)
                return []
            else:
                return acc_s

        def mutate_const_float(self, n): return []
        def mutate_const_int(self, n): return []

        def mutate_array_access(self, n: loma_ir.ArrayAccess) -> list[loma_ir.stmt]:
            base_id = get_base_id(n.array)
            if base_id and base_id in self.primal_out_arg_names_local:
                return []
            nt = getattr(n, 't', None)
            if nt is None or isinstance(nt, loma_ir.Int) or self.adj is None:
                return []
            if not base_id or base_id not in self.var_to_dvar:
                return []
            td = var_to_differential(n, self.var_to_dvar)
            acc_s = accum_deriv(td, self.adj, False, is_simd_context=False)
            if self.in_assign:
                self.adj_accum_stmts.extend(acc_s)
                return []
            else:
                return acc_s

        def mutate_struct_access(self, n: loma_ir.StructAccess) -> list[loma_ir.stmt]:
            base_id = get_base_id(n.struct)
            if base_id and base_id in self.primal_out_arg_names_local:
                return []
            nt = getattr(n, 't', None)
            if nt is None or isinstance(nt, loma_ir.Int) or self.adj is None:
                return []
            if not base_id or base_id not in self.var_to_dvar:
                return []
            td = var_to_differential(n, self.var_to_dvar)
            is_target_scalar_field = isinstance(n.t, loma_ir.Float)
            acc_s = accum_deriv(
                td, self.adj, False, self.current_func_is_simd and is_target_scalar_field)
            if self.in_assign:
                self.adj_accum_stmts.extend(acc_s)
                return []
            else:
                return acc_s

        def _apply_binary_op_rule(self, n, adj_l_fn, adj_r_fn):
            old_adj = self.adj
            s = []
            if old_adj is None:
                return []
            l_t, r_t = getattr(n.left, 't', None), getattr(n.right, 't', None)
            if l_t and not isinstance(l_t, loma_ir.Int):
                adj_l = adj_l_fn(old_adj, n.left, n.right, n.lineno)
                if adj_l:
                    self.adj = adj_l
                    s.extend(self.mutate_expr(n.left))
            if r_t and not isinstance(r_t, loma_ir.Int):
                adj_r = adj_r_fn(old_adj, n.left, n.right, n.lineno)
                if adj_r:
                    self.adj = adj_r
                    s.extend(self.mutate_expr(n.right))
            self.adj = old_adj
            return s

        def mutate_add(self, n): return self._apply_binary_op_rule(
            n, lambda adj, l, r, ln: adj, lambda adj, l, r, ln: adj)

        def mutate_sub(self, n): adj_t = getattr(self.adj, 't', loma_ir.Float()); return self._apply_binary_op_rule(
            n, lambda adj, l, r, ln: adj, lambda adj, l, r, ln: loma_ir.BinaryOp(loma_ir.Sub(), loma_ir.ConstFloat(0.0), adj, t=adj_t, lineno=ln))

        def mutate_mul(self, n):
            adj_t = getattr(self.adj, 't', loma_ir.Float())
            def mk_mul(adj, o, ln): ot = getattr(o, 't', None); o = loma_ir.Call("int2float", (o,), t=loma_ir.Float(
            ), lineno=ln) if isinstance(ot, loma_ir.Int) else o; return loma_ir.BinaryOp(loma_ir.Mul(), adj, o, t=adj_t, lineno=ln)
            return self._apply_binary_op_rule(n, lambda adj, l, r, ln: mk_mul(adj, r, ln), lambda adj, l, r, ln: mk_mul(adj, l, ln))

        def mutate_div(self, n):
            adj_t = getattr(self.adj, 't', loma_ir.Float())
            def ensure_f(e, ln): return loma_ir.Call("int2float", (e,), t=loma_ir.Float(
            ), lineno=ln) if isinstance(getattr(e, 't', None), loma_ir.Int) else e
            return self._apply_binary_op_rule(n, lambda adj, l, r, ln: loma_ir.BinaryOp(loma_ir.Div(), adj, ensure_f(r, ln), t=adj_t, lineno=ln), lambda adj, l, r, ln: loma_ir.BinaryOp(loma_ir.Div(), loma_ir.BinaryOp(loma_ir.Mul(), loma_ir.BinaryOp(loma_ir.Sub(), loma_ir.ConstFloat(0.0), adj, t=adj_t, lineno=ln), ensure_f(l, ln), t=adj_t, lineno=ln), loma_ir.BinaryOp(loma_ir.Mul(), ensure_f(r, ln), ensure_f(r, ln), t=adj_t, lineno=ln), t=adj_t, lineno=ln))

        def mutate_call(self, node: loma_ir.Call) -> list[loma_ir.stmt]:
            old_adj = self.adj
            arg_adj_s = []

            # Ensure there's an adjoint to propagate
            if old_adj is None:
                return []

            arg0 = node.args[0] if len(node.args) > 0 else None
            arg0_t = getattr(arg0, 't', None) if arg0 else None

            if node.id == 'thread_id':
                return []
            elif node.id == 'int2float' or node.id == 'float2int':
                # These functions do not propagate adjoints to their arguments
                # in the typical way as their arguments are either int or their output is int.
                pass
            elif node.id == 'sin':
                if arg0_t and not isinstance(arg0_t, loma_ir.Int):
                    # adj_arg0 = old_adj * cos(arg0)
                    cos_arg0 = loma_ir.Call(
                        'cos', (arg0,), t=loma_ir.Float(), lineno=node.lineno)
                    adj0 = loma_ir.BinaryOp(
                        loma_ir.Mul(), old_adj, cos_arg0, t=loma_ir.Float(), lineno=node.lineno)
                    self.adj = adj0
                    arg_adj_s.extend(self.mutate_expr(arg0))
                    self.adj = old_adj
            elif node.id == 'cos':
                if arg0_t and not isinstance(arg0_t, loma_ir.Int):
                    # adj_arg0 = old_adj * (-sin(arg0))
                    sin_arg0 = loma_ir.Call(
                        'sin', (arg0,), t=loma_ir.Float(), lineno=node.lineno)
                    neg_sin_arg0 = loma_ir.BinaryOp(loma_ir.Sub(), loma_ir.ConstFloat(
                        0.0), sin_arg0, t=loma_ir.Float(), lineno=node.lineno)
                    adj0 = loma_ir.BinaryOp(
                        loma_ir.Mul(), old_adj, neg_sin_arg0, t=loma_ir.Float(), lineno=node.lineno)
                    self.adj = adj0
                    arg_adj_s.extend(self.mutate_expr(arg0))
                    self.adj = old_adj
            elif node.id == 'exp':
                if arg0_t and not isinstance(arg0_t, loma_ir.Int):
                    # adj_arg0 = old_adj * exp(arg0) (node is exp(arg0))
                    adj0 = loma_ir.BinaryOp(
                        loma_ir.Mul(), old_adj, node, t=loma_ir.Float(), lineno=node.lineno)
                    self.adj = adj0
                    arg_adj_s.extend(self.mutate_expr(arg0))
                    self.adj = old_adj
            elif node.id == 'log':
                if arg0_t and not isinstance(arg0_t, loma_ir.Int):
                    # adj_arg0 = old_adj / arg0
                    adj0 = loma_ir.BinaryOp(
                        loma_ir.Div(), old_adj, arg0, t=loma_ir.Float(), lineno=node.lineno)
                    self.adj = adj0
                    arg_adj_s.extend(self.mutate_expr(arg0))
                    self.adj = old_adj
            elif node.id == 'sqrt':
                if arg0_t and not isinstance(arg0_t, loma_ir.Int):
                    # adj_arg0 = old_adj / (2 * sqrt(arg0)) (node is sqrt(arg0))
                    const_two = loma_ir.ConstFloat(2.0, lineno=node.lineno)
                    two_times_node = loma_ir.BinaryOp(
                        loma_ir.Mul(), const_two, node, t=loma_ir.Float(), lineno=node.lineno)
                    adj0 = loma_ir.BinaryOp(
                        loma_ir.Div(), old_adj, two_times_node, t=loma_ir.Float(), lineno=node.lineno)
                    self.adj = adj0
                    arg_adj_s.extend(self.mutate_expr(arg0))
                    self.adj = old_adj
            elif node.id == 'pow':
                base_expr = node.args[0]
                exp_expr = node.args[1]
                base_t = getattr(base_expr, 't', None)
                exp_t = getattr(exp_expr, 't', None)

                adj_for_pow_call = old_adj  # Save current adjoint

                # Differentiate w.r.t. base: adj_base = adj_pow * exponent * base^(exponent-1)
                if base_t and not isinstance(base_t, loma_ir.Int):
                    one_float = loma_ir.ConstFloat(1.0, lineno=node.lineno)
                    exp_minus_1 = loma_ir.BinaryOp(
                        loma_ir.Sub(), exp_expr, one_float, t=loma_ir.Float(), lineno=node.lineno)
                    pow_base_exp_minus_1 = loma_ir.Call(
                        'pow', (base_expr, exp_minus_1), t=loma_ir.Float(), lineno=node.lineno)

                    actual_exp_expr_for_mul = exp_expr
                    # Ensure exponent is float for multiplication if it was int
                    if isinstance(exp_t, loma_ir.Int):
                        actual_exp_expr_for_mul = loma_ir.Call(
                            "int2float", (exp_expr,), t=loma_ir.Float(), lineno=node.lineno)

                    term_adj_mul_exp = loma_ir.BinaryOp(loma_ir.Mul(
                    ), adj_for_pow_call, actual_exp_expr_for_mul, t=loma_ir.Float(), lineno=node.lineno)
                    adj_for_base_arg = loma_ir.BinaryOp(loma_ir.Mul(
                    ), term_adj_mul_exp, pow_base_exp_minus_1, t=loma_ir.Float(), lineno=node.lineno)

                    self.adj = adj_for_base_arg
                    arg_adj_s.extend(self.mutate_expr(base_expr))
                    self.adj = adj_for_pow_call  # Restore for next argument or outer scope

                # Differentiate w.r.t. exponent: adj_exp = adj_pow * base^exponent * log(base)
                # base^exponent is 'node'
                if exp_t and not isinstance(exp_t, loma_ir.Int):
                    log_base = loma_ir.Call(
                        'log', (base_expr,), t=loma_ir.Float(), lineno=node.lineno)
                    term_adj_mul_pow = loma_ir.BinaryOp(
                        loma_ir.Mul(), adj_for_pow_call, node, t=loma_ir.Float(), lineno=node.lineno)
                    adj_for_exp_arg = loma_ir.BinaryOp(
                        loma_ir.Mul(), term_adj_mul_pow, log_base, t=loma_ir.Float(), lineno=node.lineno)

                    self.adj = adj_for_exp_arg
                    arg_adj_s.extend(self.mutate_expr(exp_expr))
                    self.adj = adj_for_pow_call  # Restore for outer scope

                # self.adj should be restored to what it was before this pow call differentiation
                self.adj = old_adj

            elif node.id in self.func_to_rev:  # For user-defined functions
                orig_fdef = self.funcs.get(node.id)
                if not orig_fdef:
                    raise ValueError(
                        f"RDM Call Expr: Original definition for {node.id} not found.")

                rev_call_args_list = []
                # Primal inputs + their adjoint outputs
                for i, orig_arg_spec in enumerate(orig_fdef.args):
                    primal_arg_expr = node.args[i]
                    if isinstance(orig_arg_spec.i, loma_ir.In):
                        rev_call_args_list.append(primal_arg_expr)
                        if not isinstance(orig_arg_spec.t, loma_ir.Int):
                            # Ensure the primal_arg_expr is a valid LValue if we need its differential
                            if not isinstance(primal_arg_expr, (loma_ir.Var, loma_ir.ArrayAccess, loma_ir.StructAccess)):
                                # This case might need temporary variables if complex expressions are inputs,
                                # but CallNormalizeMutator should simplify arguments.
                                # For now, rely on CallNormalizeMutator.
                                pass
                            rev_call_args_list.append(var_to_differential(
                                primal_arg_expr, self.var_to_dvar))
                    elif isinstance(orig_arg_spec.i, loma_ir.Out):
                        # Adjoint input for primal output
                        if not isinstance(orig_arg_spec.t, loma_ir.Int):
                            rev_call_args_list.append(var_to_differential(
                                primal_arg_expr, self.var_to_dvar))
                        # If primal output is Int, its 'adjoint' is not typically tracked as a float differential.
                        # The reverse function signature would expect the primal Int output as an In.
                        # However, func_to_rev's signature would dictate this. Assuming simple pass-through for Int outputs.
                        # Or, if the reverse function doesn't take an adjoint for an Int output, it's omitted.
                        # Let's assume for now that Int outputs don't have corresponding float adjoints passed.

                # Adjoint input for primal return value
                if orig_fdef.ret_type and not isinstance(orig_fdef.ret_type, loma_ir.Int):
                    if old_adj:  # old_adj is the adjoint of the return value of this call
                        rev_call_args_list.append(old_adj)
                    # If no specific adj, but expected, pass 0.0
                    elif isinstance(orig_fdef.ret_type, loma_ir.Float):
                        rev_call_args_list.append(
                            loma_ir.ConstFloat(0.0, lineno=node.lineno))
                    # Else: if ret_type is struct/array and old_adj is None, it's complex.
                    # This part assumes old_adj is correctly set if the call's result was used.

                arg_adj_s.append(loma_ir.CallStmt(loma_ir.Call(
                    self.func_to_rev[node.id],
                    tuple(rev_call_args_list),
                    t=None,  # Reverse functions are void
                    lineno=node.lineno
                )))
                self.adj = old_adj  # Restore self.adj, as adjoints for inputs are handled by the rev_call

            # Note: If a call is not handled above (e.g. a new intrinsic or unmapped function)
            # it will silently not propagate adjoints through that call's arguments.

            return arg_adj_s

    return RevDiffMutator().mutate_function_def(func)
