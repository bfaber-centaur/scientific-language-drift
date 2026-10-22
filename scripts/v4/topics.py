"""V4: fixed keyword topic tags for ML sub-areas, applied identically to arXiv and ICLR title+abstract.

Multi-label: a paper can carry several tags or none. The patterns were written before looking at any
trend and are deliberately coarse. On title + abstract a tag means "mentions X" (broad); on the title
alone (prefix tt_) it means "is about X" (narrow, lower recall); `scripts/v4/topic_audit.py` prints random matches per tag for checking.
"""
from __future__ import annotations

import re

TOPICS = {
    "llm": r"large language model|\bllms?\b|\blanguage models?\b|\bgpt-?\d|chatgpt|instruction[- ]tun|"
           r"in-context learning|\bprompt(?:s|ing)?\b",
    "reasoning": r"chain[- ]of[- ]thought|\bcot\b|\breasoning\b",
    "agents": r"\bagentic\b|\b(?:llm|language|web|gui|coding|software) agents?\b|tool[- ]use|tool[- ]augmented|"
              r"multi-agent system",
    "multimodal": r"vision[- ]language|multi-?modal|\bvlms?\b|\bmllms?\b|"
                  r"text-to-image|image-text|visual question",
    "generative": r"diffusion models?|denoising diffusion|score-based|flow matching|\bgans?\b|"
                  r"generative adversarial|variational auto-?encoder|\bvaes?\b|normali[sz]ing flows?",
    "rl": r"reinforcement learning|\brl\b|policy gradient|q-learning|markov decision|\bmdps?\b|bandit",
    "alignment_safety": r"\balignment\b|\brlhf\b|\bsafety\b|jailbreak|red[- ]teaming|harmful|toxicity|"
                        r"preference optimi[sz]ation|\bdpo\b|reward model",
    "interpretability": r"interpretab|explainab|\bxai\b|mechanistic|saliency|feature attribution|"
                        r"\bprobing\b|sparse auto-?encoder",
    "graph": r"graph neural|\bgnns?\b|graph representation|node classification|link prediction|"
             r"message[- ]passing|knowledge graph",
    "federated_privacy": r"federated|differential(?:ly)? privacy|differentially private|privacy-preserving|"
                         r"membership inference|machine unlearning",
    "robustness": r"adversarial (?:attack|example|perturbation|robust|training)|\brobustness\b|"
                  r"out-of-distribution|\bood\b|distribution shift|domain generali[sz]ation|domain adaptation",
    "theory_optimization": r"convergence rate|generali[sz]ation bound|sample complexity|\bregret\b|"
                           r"non-?convex|stochastic gradient|\bsgd\b|we prove|theoretical analysis|"
                           r"\btheorem\b|provabl|minimax",
    "vision_3d_seg": r"object detection|segmentation|\b3d\b|point clouds?|\bnerfs?\b|neural radiance|"
                     r"gaussian splatting|pose estimation|depth estimation",
    "video": r"\bvideos?\b",
    "speech_audio": r"\bspeech\b|\baudio\b|\basr\b|speaker|\bmusic\b",
    "time_series": r"time[- ]series|forecasting",
    "science": r"molecul|protein|drug discovery|materials? (?:science|discovery|design)|physics-informed|"
               r"partial differential|\bpdes?\b|chemi(?:cal|stry)|genom|single-cell|climate|weather",
    "medical": r"medical|clinical|patients?\b|healthcare|radiolog|\bmri\b|\behrs?\b|pathology",
    "robotics_driving": r"\brobot|manipulation task|embodied|locomotion|autonomous driving|self-driving",
    "efficiency": r"quantiz|pruning|knowledge distillation|model compression|low-rank adaptation|\blora\b|"
                  r"mixture[- ]of[- ]experts|\bmoe\b|efficient inference|speculative decoding|kv cache",
    "self_supervised": r"self-supervised|contrastive learning|representation learning|masked (?:image|auto)",
    "continual_meta_fewshot": r"continual learning|lifelong learning|catastrophic forgetting|meta-learning|"
                              r"few-shot",
    "retrieval_recsys": r"retrieval-augmented|\brag\b|recommend(?:er|ation)|information retrieval|"
                        r"dense retrieval",
    "classic_nlp": r"machine translation|named entity|sentiment|question answering|summari[sz]ation|"
                   r"text classification",
    "causal": r"\bcausal(?:ity)?\b(?! (?:attention|mask|language model|transformer|decoder))",
    "fairness": r"\bfairness\b|\bfair\b|\bdemographic|\bsocial bias|gender bias",
    "benchmark_dataset": r"\bbenchmark(?:s|ing)?\b|we (?:introduce|present|release|construct|curate) "
                         r"(?:a |an )?(?:new |novel |large-scale )?(?:dataset|benchmark|corpus)",
}
_RX = {k: re.compile(v) for k, v in TOPICS.items()}


def tag(text: str, prefix: str = "t_") -> dict:
    t = (text or "").lower()
    return {prefix + k: bool(rx.search(t)) for k, rx in _RX.items()}
