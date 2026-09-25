---
permalink: /
title: "Ross Jacobucci"
seo_title: "Ross Jacobucci — Digital Health & Machine Learning"
excerpt: "Machine learning scientist working on measurement, prediction, and adaptive interventions for mental health. I lead a $6.6M ARPA-H program (team of 20) and a lab that processes 7.4M+ smartphone screenshots, fine-tunes and evaluates vision-language models, runs randomized trials of digital interventions, and builds the evaluation tooling to decide what to deploy."
author_profile: true
redirect_from:
  - /about/
  - /about.html
header:
  overlay_color: "#142a45"
  overlay_filter: "0.0"
  eyebrow: "Digital health · Data science · Research"
  cta_label: "Explore my work"
  cta_url: /work/
  downloads: true
---

<dl class="work-metrics" aria-label="Selected work at a glance">
  <div><dt>$6.6M</dt><dd>ARPA-H program · team of 20</dd></div>
  <div><dt>7.4M+</dt><dd>Smartphone screenshots processed</dd></div>
  <div><dt>15 GPUs</dt><dd>Fine-tuning &amp; inference infrastructure</dd></div>
  <div><dt>10,000+</dt><dd>Person-days in a micro-randomized trial</dd></div>
</dl>

## Selected Work

<div class="research-grid">
  <a class="research-card" href="/work/#screenshot-models">
    <div class="research-card__tag">Applied ML &amp; evaluation</div>
    <h3>From screenshots to risk signals</h3>
    <p>OCR and vision-language classification across 7.4M+ screenshots, with Qwen fine-tuning, user-grouped validation, and held-out evaluation in a restricted data environment.</p>
  </a>
  <a class="research-card" href="/work/#adaptive-interventions">
    <div class="research-card__tag">Experiments &amp; personalization</div>
    <h3>When and for whom to intervene</h3>
    <p>Factorial experiments and a 380-person micro-randomized trial. Causal analyses translated into deployment rules for message timing and targeting.</p>
  </a>
  <a class="research-card" href="/publications/#machine-learning-and-methodology">
    <div class="research-card__tag">Methodology</div>
    <h3>ML in clinical psychology</h3>
    <p>How measurement quality and analytic choices shape the reliability of machine learning applied to psychological data. Influential commentaries in <em>Clinical Psychological Science</em> and <em>Perspectives on Psychological Science</em>.</p>
  </a>
  <a class="research-card" href="/publications/#regularized-structural-equation-modeling">
    <div class="research-card__tag">RegSEM</div>
    <h3>Regularized structural equation modeling</h3>
    <p>A decade of work extending regularization (lasso, elastic net, stability selection) to latent-variable models, beginning with the original 2016 paper and the <code>regsem</code> R package.</p>
  </a>
</div>

## Research Program

**Digital phenotyping and suicide risk.** I build models that turn passively collected smartphone and wearable data into measures of mental health and near-term risk. My lab has processed 7.4M+ screenshots and built a 15-GPU fine-tuning and inference stack using PyTorch, Hugging Face PEFT, Unsloth, vLLM, and SGLang. This work includes studies in *JAMA Network Open*, *npj Digital Medicine*, and *JMIR Mental Health*. [Projects, tools, and outputs →](/work/#screenshot-models)

**Experiments and adaptive interventions.** I led causal and personalization analyses of two factorial-trial cohorts (about 760 participants each) and a nested 380-person micro-randomized trial, delivering deployment rules for message timing and targeting. I also designed a Phase 2 bandit-driven just-in-time adaptive intervention (JITAI) and its simulation study. [Experiment details →](/work/#adaptive-interventions)

**Multimodal measurement at scale.** As PI of the $6.6M ARPA-H EVIDENT award, I lead a team of 20 and designed the protocol and measurement stack for a 1,500-person randomized trial and a 300-person observational cohort. The program combines wearable, smartphone, video, and momentary-assessment data, with vendor selection, data-security review, and participant safety built into the study design. [Program scope →](/work/#multimodal-program)

**Ecological momentary assessment and intensive longitudinal data.** Much of my methodological work concerns the analysis of intensive longitudinal data collected from clinical populations — handling momentary missingness, zero inflation, continuous-time dynamics, and computerized adaptive testing for in-the-moment risk assessment.

**Regularized structural equation modeling.** Beginning with the original *Regularized Structural Equation Modeling* paper (2016) and the `regsem` R package, I have contributed to a line of work extending regularization (lasso, elastic net, stability selection) to latent-variable models, and to understanding how measurement quality shapes the conclusions of machine learning applied to psychological data.

**Machine learning methodology in psychology.** A second methodological strand examines the reliability of machine learning claims in clinical psychology — including a frequently-cited commentary in *Clinical Psychological Science* on inflated prediction performance in suicide risk modeling, and a paper in *Perspectives on Psychological Science* on the often-overlooked role of measurement error in machine learning applications.

> **Book.** [*Machine Learning for Social and Behavioral Research*](/book/) (Guilford Press, 2023), with Kevin Grimm and Zhiyong Zhang — part of the *Methodology in the Social Sciences* series.

## Background

I joined the Center for Healthy Minds at the University of Wisconsin–Madison in 2024. From 2017 to 2024 I was Assistant Professor of Psychology at the University of Notre Dame. I received my PhD in Psychology from the University of Southern California in 2017.

## Contact

<div class="contact-row">
  <a class="contact-pill contact-pill--primary" href="mailto:rcjacobuc@gmail.com">rcjacobuc@gmail.com</a>
  <a class="contact-pill" href="https://www.linkedin.com/in/ross-jacobucci-7018b05b/">LinkedIn</a>
  <a class="contact-pill" href="{{ site.resume_url }}">Download resume (PDF)</a>
  <a class="contact-pill" href="{{ site.cv_url }}">Download CV (PDF)</a>
  <a class="contact-pill" href="https://scholar.google.com/citations?user=K7_cclwAAAAJ&hl=en">Google Scholar</a>
  <a class="contact-pill" href="https://github.com/Rjacobucci">GitHub</a>
</div>

For university correspondence: [jacobucci@wisc.edu](mailto:jacobucci@wisc.edu).
