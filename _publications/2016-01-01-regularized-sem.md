---
title: "Regularized Structural Equation Modeling"
collection: publications
permalink: /publication/2016-regularized-sem
excerpt: 'Foundational paper introducing RegSEM methodology, extending regularization techniques to structural equation models.'
date: 2016-07-01
venue: 'Structural Equation Modeling'
citation: 'Jacobucci, R., Grimm, K. J., & McArdle, J. J. (2016). &quot;Regularized Structural Equation Modeling.&quot; <i>Structural Equation Modeling</i>, 23(4), 555-566.'
---

## Abstract

We present a new method that extends the use of regularization in both lasso and ridge regression to structural equation modeling (SEM). This method, termed regularized structural equation modeling (RegSEM), penalizes specific parameters in structural equation models, with the goal of creating easier to understand and simpler models.

## Key Innovation

**RegSEM extends regularization to SEM by:**
- Implementing both ridge and lasso penalties in structural equation models
- Enabling automatic parameter selection and model simplification
- Addressing overfitting in complex models with small samples
- Focusing on model generalizability rather than just model fit

## Technical Contributions

- **Parameter Penalties**: Ridge and lasso regularization for any SEM parameter
- **Model Selection**: Automated approach to identifying important parameters
- **Sparse Solutions**: Lasso penalties can set parameters exactly to zero
- **Generalizability Focus**: Emphasis on cross-validation and out-of-sample prediction

## Research Impact

- **Most Cited Work**: Foundation for extensive follow-up research
- **R Package**: The `regsem` package has become a standard tool in the field
- **Methodological Advance**: Addresses replication crisis through generalizability emphasis
- **Field Influence**: Sparked numerous applications and extensions

## Practical Applications

RegSEM is particularly useful for:
- Large models with many parameters
- Small sample sizes relative to model complexity
- Exploratory model building
- Cross-validation and prediction contexts
- Addressing multicollinearity in SEM

## Software Implementation

The method is implemented in the R package `regsem`, making it accessible to applied researchers. The package integrates with `lavaan` for easy implementation.

Recommended citation: Jacobucci, R., Grimm, K. J., & McArdle, J. J. (2016). "Regularized Structural Equation Modeling." <i>Structural Equation Modeling</i>, 23(4), 555-566.