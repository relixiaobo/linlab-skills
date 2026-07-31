# Statistical Methods

Use this reference for formal tests, regression, uncertainty, and effect sizes.

## First Diagnose

Before choosing a method:

- Is the question descriptive, inferential, predictive, or causal?
- What is the outcome variable type?
- What is the predictor/treatment variable type?
- What is the unit of analysis?
- Are observations independent, clustered, paired, or repeated?
- What is the sample size by group?
- Are missing values likely MCAR, MAR, or MNAR?
- Is this exploratory or confirmatory?

## Common Method Map

| Question | Typical method |
| --- | --- |
| Two groups, continuous outcome | t-test, Welch t-test, Mann-Whitney, regression |
| 3+ groups, continuous outcome | ANOVA, Welch ANOVA, Kruskal-Wallis, regression |
| Two categorical variables | Chi-square, Fisher exact, logistic regression |
| Two continuous variables | Pearson/Spearman correlation, regression |
| Binary outcome | Logistic regression |
| Count outcome | Poisson/negative binomial regression |
| Repeated measures | Paired test, mixed-effects model |
| Time-to-event | Kaplan-Meier, Cox model |
| Prediction | Train/test split or cross-validation; compare against baseline |
| Observational causal effect | Matching, DiD, IV, RDD, sensitivity analysis |

## Reporting Rules

Report:

- Point estimate.
- Uncertainty: CI, SE, or credible interval.
- Effect size.
- Sample size and exclusions.
- Assumption checks.
- Practical significance.
- Limitations.

Do not report only a p-value.

## Assumption Failures

If assumptions fail:

- Use Welch instead of equal-variance t-test.
- Use robust standard errors for heteroscedasticity.
- Use non-parametric methods when distribution assumptions are not defensible.
- Transform only when it preserves interpretability or report both scales.
- For outliers, run sensitivity with and without them; do not silently drop.

## Causality

Only use causal language when design supports it. Otherwise say "associated with" and list confounders.

