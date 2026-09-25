---
title: "Selected Work"
permalink: /work/
excerpt: "Digital mental health research spanning clinical measurement, risk prediction, randomized experiments, adaptive interventions, and open-source statistical software."
author_profile: false
wide: true
reading_width: true
compact_profile: true
---

My work connects three questions: are we measuring meaningful change, can we predict risk, and which interventions help? I develop the statistical methods, models, and experiments needed to answer them with behavioral data.

<nav class="work-index" aria-label="Areas of work on this page">
  <a href="#measurement-and-prediction">Measurement &amp; prediction</a>
  <a href="#adaptive-interventions">Experiments &amp; interventions</a>
  <a href="#research-software">Methods &amp; software</a>
</nav>

## Measurement and prediction
{: #measurement-and-prediction }

Clinical prediction starts with the quality of the signal. My work combines passive sensing and self-report with psychometrics, adaptive assessment, and longitudinal models to study mental health as it changes in daily life.

### EVIDENT: measuring rapid clinical change
{: #multimodal-program }

<p class="project-meta">Principal Investigator · $6.6M ARPA-H award · Team of 20 · Ongoing, 2026–2028</p>

I lead a multimodal behavioral-health program combining Empatica and Garmin wearables, Android and iOS passive sensing, video, and ecological momentary assessment (EMA). I designed the protocol and measurement stack, selected vendors and data platforms, and led IRB, legal, and data-security review.

**Study design:** a 1,500-person randomized trial and a 300-person observational cohort. These are planned study sizes; the program's work spans measurement development and study operations, not yet a completed outcome evaluation.

[Award and research roles in my CV (PDF)]({{ site.cv_url }})

### From smartphone screenshots to risk signals
{: #screenshot-models }

<p class="project-meta">7.4M+ screenshots processed · Prospective model evaluation · Restricted data environment</p>

I processed smartphone screenshots with OCR and vision-language classification to detect suicide-related language and predict momentary suicidal ideation. I also built a fine-tuning and inference stack on a 15-GPU L40S cluster, using Qwen, LoRA/PEFT, Unsloth, vLLM, and SGLang.

The model-selection harness uses user-grouped cross-validation, a lockbox test set, and promotion gates. The screenshot work produced a prospective machine learning study in *JMIR Mental Health*; related studies examined nighttime phone use and screenshot-derived screen time as markers of suicide risk.

[Vision-language model study](https://mental.jmir.org/2026/1/e90581) · [Related digital-phenotyping publications](/publications/#digital-phenotyping-and-suicide-risk)

### Adaptive assessment and longitudinal data

My collaborative work includes a multidimensional computerized adaptive test for momentary suicide-risk assessment, and studies of survey burden, compliance, missingness, and within-person dynamics. These address a practical measurement question: how much useful information can we collect without imposing unnecessary burden?

[Adaptive assessment: development and usability study](https://formative.jmir.org/2025/1/e76544/)

## Experiments and adaptive interventions
{: #adaptive-interventions }

<p class="project-meta">Two factorial-trial cohorts · ~760 participants each · Nested MRT: 380 participants, 10,000+ person-days</p>

**My role.** I led causal and personalization analyses of two factorial-trial cohorts (2⁴ and 2⁶ designs) and a nested micro-randomized trial (MRT). I estimated causal excursion effects, examined differences in treatment response using causal forests and policy trees, and tested whether findings transported across cohorts.

**Decision delivered.** The completed analyses produced deployment rules for message timing and targeting. For Phase 2, I designed a bandit-driven just-in-time adaptive intervention (JITAI) and its simulation study.

**Related ongoing collaborations.** My digital-intervention work also includes co-investigator roles on an NIH-funded study of human and digital support in a meditation app for depression and anxiety, and a Templeton-funded program on personalized well-being interventions. I am an MPI on a project developing just-in-time support for outpatient suicide care. These are separate projects with distinct research roles and stages.

[Funding and collaboration details in my CV (PDF)]({{ site.cv_url }})

## Reliable methods and research software
{: #research-software }

I develop and co-develop statistical software for problems that recur across behavioral research: selecting variables, modeling change over time, and identifying differences between people.

<ul class="software-list">
  <li>
    <h3><a href="https://cran.r-project.org/package=regsem">regsem</a></h3>
    <p>Regularization and cross-validation for structural equation models.</p>
    <a href="https://github.com/Rjacobucci/regsem/">Source code →</a>
  </li>
  <li>
    <h3><a href="https://cran.r-project.org/package=MplusTrees">MplusTrees</a></h3>
    <p>Co-developed software for recursive partitioning with structural equation models fit in Mplus.</p>
  </li>
  <li>
    <h3><a href="https://cran.r-project.org/package=longRPart2">longRPart2</a></h3>
    <p>Recursive partitioning of linear and nonlinear mixed-effects models for longitudinal data.</p>
    <a href="https://github.com/Rjacobucci/longRPart2">Source code →</a>
  </li>
</ul>

### What makes a model result credible?

My methodological work examines inflated prediction performance in suicide machine learning and the effect of measurement error on ML conclusions. This work informs the checks I build into model evaluation, alongside the development of regularized latent-variable models.

[Inflated prediction performance](https://doi.org/10.1177/2167702620954216) · [Measurement and machine learning](https://doi.org/10.1177/1745691620902467)

<details class="methodology-details" markdown="1">
<summary>More on longitudinal modeling and methodological foundations</summary>

**Ecological momentary assessment and intensive longitudinal data.** Much of my methodological work concerns the analysis of intensive longitudinal data collected from clinical populations — handling momentary missingness, zero inflation, continuous-time dynamics, and computerized adaptive testing for in-the-moment risk assessment.

**Regularized structural equation modeling.** Beginning with the original *Regularized Structural Equation Modeling* paper (2016) and the `regsem` R package, I have contributed to a line of work extending regularization (lasso, elastic net, stability selection) to latent-variable models, and to understanding how measurement quality shapes the conclusions of machine learning applied to psychological data.

**Machine learning methodology in psychology.** A second methodological strand examines the reliability of machine learning claims in clinical psychology — including a frequently-cited commentary in *Clinical Psychological Science* on inflated prediction performance in suicide risk modeling, and a paper in *Perspectives on Psychological Science* on the often-overlooked role of measurement error in machine learning applications.

</details>

I co-authored [*Machine Learning for Social and Behavioral Research*](/book/) (Guilford, 2023), recipient of the 2025 Barbara Byrne Award for Outstanding Book from the Society of Multivariate Experimental Psychology. I have also taught applied deep learning with Python and advanced machine learning through Statistical Horizons.

## Get in touch

I am interested in industry data science and research roles in digital health, measurement, and experimentation. My technical work spans Python (PyTorch, scikit-learn, pandas), R, SQL, Git, and Linux/HPC.

<div class="contact-row">
  <a class="contact-pill contact-pill--primary" href="mailto:rcjacobuc@gmail.com">rcjacobuc@gmail.com</a>
  <a class="contact-pill" href="{{ site.resume_url }}">Download resume (PDF)</a>
  <a class="contact-pill" href="{{ site.cv_url }}">Download CV (PDF)</a>
  <a class="contact-pill" href="https://www.linkedin.com/in/ross-jacobucci-7018b05b/">LinkedIn</a>
</div>
