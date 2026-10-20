Build an Excel pricing model from `input/pricing_inputs.csv` and deliver it as
`pricing-model.xlsx`. Create visible `README`, `Inputs`, `Calculations`,
`Outputs`, and `Checks` worksheets. Preserve every source row and value in
`Inputs`. In `Calculations`, keep every plan and use live formulas, not hardcoded
outputs, for gross monthly revenue (`base_price * seats`), discount amount,
net monthly revenue, and first-year total (`net monthly revenue * AnnualMonths +
setup_fee`). Define the workbook-level name `AnnualMonths` with value 12 and add
meaningful formula checks in `Checks`. In your delivery response, state whether
a real spreadsheet engine recalculated the workbook and any remaining limits.
