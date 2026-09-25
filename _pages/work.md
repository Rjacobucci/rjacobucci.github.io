---
title: "Selected Work"
permalink: /work/
excerpt: "Applied machine learning and digital health research: screenshot-based models, randomized experiments, adaptive interventions, multimodal measurement, and open-source evaluation tools."
author_profile: true
---

I build models, experiments, and measurement systems for mental health. My work connects large-scale behavioral data with careful evaluation: what a model can predict, whether an intervention helps, and what evidence should guide deployment.

<nav class="work-index" aria-label="Projects on this page">
  <a href="#screenshot-models">Applied ML</a>
  <a href="#adaptive-interventions">Experiments</a>
  <a href="#multimodal-program">Program leadership</a>
  <a href="#research-software">Research software</a>
</nav>

## From smartphone screenshots to risk signals
{: #screenshot-models }

<p class="project-meta">7.4M+ screenshots processed · 15-GPU L40S cluster · Restricted data environment</p>

**The problem.** Smartphone screenshots capture behavior in daily life, but turning millions of sensitive images into useful measures requires both a scalable processing pipeline and evaluation that keeps a person's data from leaking across training and test sets.

**What I built.** I processed 7.4M+ screenshots with OCR and vision-language classification on an HPC cluster to detect suicide-related language and predict momentary suicidal ideation. I also built the lab's LLM fine-tuning and inference stack: LoRA fine-tuning of open vision-language models, including Qwen, with Hugging Face PEFT and Unsloth; inference with vLLM and SGLang; and a model-selection harness with user-grouped cross-validation, a lockbox test set, and promotion gates.

**Outputs.** The screenshot work produced a prospective machine learning study in *JMIR Mental Health* (2026). Related work linked screenshot-derived screen time to daily suicide risk (*npj Digital Medicine*, 2025) and passively logged nighttime phone use to next-day risk (*JAMA Network Open*, 2025). This work focuses on research models and prospective evaluation.

**Tools & methods:** Python, PyTorch, Hugging Face Transformers/PEFT, Unsloth, Qwen, vLLM, SGLang, OCR, Linux/HPC, grouped validation.

[Related publications →](/publications/#digital-phenotyping-and-suicide-risk)

## Experiments that inform when and for whom to intervene
{: #adaptive-interventions }

<p class="project-meta">Two factorial-trial cohorts · ~760 participants each · Nested MRT: 380 participants, 10,000+ person-days</p>

**The problem.** An average treatment effect is not enough to decide which intervention components to use, who should receive a message, or when to send it. Those decisions require randomized evidence about timing and differences in response.

**My role.** I led the causal and personalization analyses of two factorial-trial cohorts (2⁴ and 2⁶ designs) and a nested micro-randomized trial (MRT). I estimated causal excursion effects, examined heterogeneous treatment effects with causal forests and policy trees, and tested whether findings transported across cohorts.

**Decision delivered.** The completed analyses produced deployment rules for message timing and targeting. For Phase 2, I designed a bandit-driven just-in-time adaptive intervention (JITAI) and its simulation study.

**Methods:** Factorial experiments, micro-randomization, causal excursion effects, causal forests, policy learning, cross-cohort transport tests, bandits for adaptive interventions.

## Leading a multimodal behavioral health program
{: #multimodal-program }

<p class="project-meta">$6.6M ARPA-H EVIDENT award · Principal Investigator · Team of 20 · 2026–2028</p>

**The problem.** Measuring rapid clinical change in behavioral health requires a coordinated measurement system across devices, data platforms, study operations, and participant-safety procedures.

**What I lead.** I designed the protocol and measurement stack for a 1,500-person randomized trial and a 300-person observational cohort, combining Empatica and Garmin wearables, Android and iOS passive sensing, video, and ecological momentary assessment (EMA). I selected vendors and data platforms and led IRB, legal, and data-security review.

**Deliverable & stage.** An ongoing program with a planned combined study size of 1,800 participants. My contributions span the protocol, measurement stack, vendor selection, and IRB, legal, and data-security review for the randomized and observational studies.

**Scope:** Multimodal data collection, longitudinal measurement, vendor evaluation, study operations, restricted-data workflows, and cross-functional research leadership.

## Reusable research software and credible model evaluation
{: #research-software }

<p class="project-meta">400K+ combined downloads across regsem, MplusTrees, and longRPart2</p>

**The problem.** Predictive performance depends on measurement quality and analytic choices. Reusable statistical tools and explicit checks on inflated performance help make those choices inspectable.

**What I built.** I authored R packages for regularized structural equation modeling and tree-based analysis of longitudinal data, including `regsem`, `MplusTrees`, and `longRPart2`. The regularized SEM work extends lasso, elastic net, and stability selection to latent-variable models.

**Outputs.** These tools have more than 400,000 combined downloads. My methodological work also examines inflated prediction performance in suicide machine learning and the effect of measurement error on ML conclusions—questions that directly inform how I evaluate models. I co-authored *Machine Learning for Social and Behavioral Research* to make these methods usable by researchers.

**Tools & methods:** R, regularization, structural equation modeling, longitudinal models, tree-based methods, psychometrics, model evaluation.

[Software on GitHub](https://github.com/Rjacobucci) · [Evaluation and methodology publications](/publications/#machine-learning-and-methodology) · [Book](/book/)

## Background & contact

I am a quantitative psychologist and machine learning scientist at the Center for Healthy Minds, University of Wisconsin–Madison. My technical work spans Python (PyTorch, scikit-learn, pandas), R, SQL, Git, and Linux/HPC. I am interested in industry data science and research roles in digital health, model evaluation, and experimentation.

<div class="contact-row">
  <a class="contact-pill contact-pill--primary" href="mailto:rcjacobuc@gmail.com">Get in touch</a>
  <a class="contact-pill" href="{{ site.resume_url }}">Download resume (PDF)</a>
  <a class="contact-pill" href="{{ site.cv_url }}">Download CV (PDF)</a>
  <a class="contact-pill" href="https://www.linkedin.com/in/ross-jacobucci-7018b05b/">LinkedIn</a>
</div>
