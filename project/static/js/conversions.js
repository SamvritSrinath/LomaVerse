document.addEventListener('DOMContentLoaded', () => {
  // Mass Conversion Elements
  const massValueInput = document.getElementById('massValue');
  const massFromUnitSelect = document.getElementById('massFromUnit');
  const massToUnitSelect = document.getElementById('massToUnit');
  const massResultDiv = document.getElementById('massResult');
  const copyMassResultButton = document.getElementById('copyMassResult');

  // Velocity Conversion Elements
  const velocityValueInput = document.getElementById('velocityValue');
  const velocityFromUnitSelect = document.getElementById('velocityFromUnit');
  const velocityToUnitSelect = document.getElementById('velocityToUnit');
  const velocityResultDiv = document.getElementById('velocityResult');
  const copyVelocityResultButton =
    document.getElementById('copyVelocityResult');

  // Constants
  const KG_PER_SOLAR_MASS = 1.98847e30;
  const AU_PER_KM = 1 / 1.495978707e8;
  const YEARS_PER_SECOND = 1 / 3.15576e7;
  const AU_YEAR_PER_KM_S = AU_PER_KM / YEARS_PER_SECOND; // km/s to AU/year
  const AU_YEAR_PER_AU_DAY = 365.25; // AU/day to AU/year

  function convertMass() {
    const value = parseFloat(massValueInput.value);
    const fromUnit = massFromUnitSelect.value;
    const toUnit = massToUnitSelect.value;
    let resultText = 'Invalid input or conversion.';

    if (isNaN(value)) {
      massResultDiv.textContent = 'Please enter a valid number.';
      return;
    }

    let resultNumeric;
    if (fromUnit === toUnit) resultNumeric = value;
    else if (fromUnit === 'solarmass' && toUnit === 'kg')
      resultNumeric = value * KG_PER_SOLAR_MASS;
    else if (fromUnit === 'kg' && toUnit === 'solarmass')
      resultNumeric = value / KG_PER_SOLAR_MASS;

    if (typeof resultNumeric !== 'undefined') {
      resultText = resultNumeric.toExponential(5);
    }
    massResultDiv.textContent = resultText;
  }

  function convertVelocity() {
    const value = parseFloat(velocityValueInput.value);
    const fromUnit = velocityFromUnitSelect.value;
    const toUnit = velocityToUnitSelect.value;
    let resultText = 'Invalid input or conversion.';

    if (isNaN(value)) {
      velocityResultDiv.textContent = 'Please enter a valid number.';
      return;
    }

    let valueInAuYear; // Convert input to base unit (AU/year)

    if (fromUnit === 'au_year') valueInAuYear = value;
    else if (fromUnit === 'km_s') valueInAuYear = value * AU_YEAR_PER_KM_S;
    else if (fromUnit === 'au_day') valueInAuYear = value * AU_YEAR_PER_AU_DAY;
    else {
      velocityResultDiv.textContent = resultText;
      return;
    }

    let resultNumeric;
    if (toUnit === 'au_year') resultNumeric = valueInAuYear;
    else if (toUnit === 'km_s')
      resultNumeric = valueInAuYear / AU_YEAR_PER_KM_S;
    else if (toUnit === 'au_day')
      resultNumeric = valueInAuYear / AU_YEAR_PER_AU_DAY;

    if (typeof resultNumeric !== 'undefined') {
      // For velocities, scientific notation might be too much if numbers are small
      if (
        Math.abs(resultNumeric) > 1e5 ||
        (Math.abs(resultNumeric) < 1e-3 && resultNumeric !== 0)
      ) {
        resultText = resultNumeric.toExponential(5);
      } else {
        resultText = parseFloat(resultNumeric.toFixed(5)).toString(); // Show reasonable precision
      }
    }
    velocityResultDiv.textContent = resultText;
  }

  function copyToClipboard(text, buttonElement) {
    const originalButtonText = buttonElement.textContent;
    if (!navigator.clipboard) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand('copy');
        buttonElement.textContent = 'Copied!';
      } catch (err) {
        buttonElement.textContent = 'Failed!';
        console.error('Fallback copy failed', err);
      }
      document.body.removeChild(textArea);
    } else {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          buttonElement.textContent = 'Copied!';
        })
        .catch(err => {
          buttonElement.textContent = 'Failed!';
          console.error('Async copy failed', err);
        });
    }
    setTimeout(() => {
      buttonElement.textContent = originalButtonText;
    }, 1500);
  }

  // Mass Conversion Listeners
  if (massValueInput) massValueInput.addEventListener('input', convertMass);
  if (massFromUnitSelect)
    massFromUnitSelect.addEventListener('change', convertMass);
  if (massToUnitSelect)
    massToUnitSelect.addEventListener('change', convertMass);
  if (copyMassResultButton)
    copyMassResultButton.addEventListener('click', () => {
      const result = massResultDiv.textContent;
      if (
        result &&
        !result.startsWith('Please') &&
        !result.startsWith('Invalid')
      )
        copyToClipboard(result, copyMassResultButton);
    });

  // Velocity Conversion Listeners
  if (velocityValueInput)
    velocityValueInput.addEventListener('input', convertVelocity);
  if (velocityFromUnitSelect)
    velocityFromUnitSelect.addEventListener('change', convertVelocity);
  if (velocityToUnitSelect)
    velocityToUnitSelect.addEventListener('change', convertVelocity);
  if (copyVelocityResultButton)
    copyVelocityResultButton.addEventListener('click', () => {
      const result = velocityResultDiv.textContent;
      if (
        result &&
        !result.startsWith('Please') &&
        !result.startsWith('Invalid')
      )
        copyToClipboard(result, copyVelocityResultButton);
    });

  // Initial conversions on load if values are present
  if (massValueInput && massValueInput.value) convertMass();
  if (velocityValueInput && velocityValueInput.value) convertVelocity();
});
