import traceback

try:
    import spacy
    # Load the small English pipeline
    nlp = spacy.load("en_core_web_sm")
except ImportError:
    print("[NLP] Spacy is not installed. To enable auto-learning:")
    print("      Run: pip install spacy")
    print("      Run: python -m spacy download en_core_web_sm")
    nlp = None
except OSError:
    print("[NLP] Spacy model 'en_core_web_sm' is not installed. To enable auto-learning:")
    print("      Run: python -m spacy download en_core_web_sm")
    nlp = None
except Exception as e:
    print(f"[NLP] Failed to initialize spacy: {e}")
    nlp = None


def extract_facts(text):
    """
    Uses Spacy dependency parsing to extract declarative facts about the user.
    Examples:
        "My favorite color is blue" -> "User's favorite color is blue"
        "I am a software engineer" -> "User is a software engineer"
        "I live in New York" -> "User lives in New York"
        "I like eating pizza" -> "User likes eating pizza"
    """
    if not nlp:
        return []

    try:
        doc = nlp(text)
        facts = []

        for sent in doc.sents:
            # Rule 1: "My [noun] is [value]"
            root = sent.root
            if root.lemma_ == "be":
                subj = None
                attr = None
                for child in root.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        subj = child
                    if child.dep_ in ("attr", "acomp"):
                        attr = child
                
                if subj and attr:
                    has_my = any(t.text.lower() == "my" for t in subj.subtree)
                    if has_my:
                        subj_text = " ".join([t.text for t in subj.subtree if t.text.lower() != "my"]).strip()
                        # Fix formatting for 's (e.g. "dog 's name" -> "dog's name")
                        subj_text = subj_text.replace(" 's", "'s")
                        attr_text = " ".join([t.text for t in attr.subtree]).strip()
                        fact = f"User's {subj_text} is {attr_text}"
                        fact = " ".join(fact.split())
                        facts.append(fact)

            # Rule 2: "I [verb] [complements]"
            for token in sent:
                if token.dep_ == "nsubj" and token.text.lower() == "i":
                    verb = token.head
                    
                    if verb.lemma_ == "be":
                        # "I am X"
                        for child in verb.children:
                            if child.dep_ in ("attr", "acomp"):
                                attr_text = " ".join([t.text for t in child.subtree]).strip()
                                facts.append(f"User is {attr_text}")
                                break
                    else:
                        # Action verbs like want, like, live, work
                        verb_lemma = verb.lemma_
                        # Filter to a specific set of strong preference/state verbs to reduce noise
                        if verb_lemma in ("want", "need", "like", "love", "hate", "live", "work", "study", "play", "enjoy", "prefer"):
                            complements = []
                            for child in verb.children:
                                if child.dep_ in ("dobj", "prep", "xcomp", "acomp"):
                                    complements.append(" ".join([t.text for t in child.subtree]))
                            
                            if complements:
                                comp_text = " ".join(complements).strip()
                                # Handle third-person singular (s / es)
                                suffix = "es" if verb_lemma.endswith(("s", "sh", "ch", "x", "z", "o")) else "s"
                                fact = f"User {verb_lemma}{suffix} {comp_text}"
                                fact = " ".join(fact.split())
                                facts.append(fact)

        return facts
    except Exception as e:
        print(f"[NLP] Error extracting facts: {e}")
        return []

if __name__ == "__main__":
    # Test cases
    test_sentences = [
        "My favorite color is blue.",
        "My dog's name is Rex.",
        "I am a software engineer.",
        "I live in New York City.",
        "I like to eat pizza.",
        "I love watching movies on weekends.",
        "I need a new laptop.",
        "Turn off the lights."  # Should extract nothing
    ]
    for s in test_sentences:
        res = extract_facts(s)
        print(f"{s} -> {res}")
