"""Subword-Alignment: Wort-Labels auf die Subword-Tokens des Modells mappen.

Unsere Labels gelten pro Wort, die Modelle arbeiten aber auf Subwords
("Rinderhackfleisch" -> mehrere Tokens). Konvention wie im Proposal:
das erste Subword eines Wortes trägt das Label, alle weiteren bekommen -100.

Warum -100? Das ist der ignore_index von PyTorchs CrossEntropyLoss – diese
Positionen fließen weder in den Loss noch in die Metriken ein. Wer hier
versehentlich 0 ("O") statt -100 setzt, trainiert das Modell darauf,
Wortfortsetzungen als "kein Entity" zu klassifizieren, und wundert sich
später über die Evaluation.
"""

from magda.labels import label2id

IGNORE_INDEX = -100


def align_word_labels(word_ids: list[int | None], word_tags: list[str]) -> list[int]:
    """Erzeugt die Label-ID-Folge für eine tokenisierte Sequenz.

    word_ids kommt von tokenizer(..., is_split_into_words=True).word_ids():
    pro Token der Index des Ursprungsworts, None für Sondertokens ([CLS] etc.).
    """
    labels = []
    previous_word = None
    for word_id in word_ids:
        if word_id is None:
            # Sondertokens ([CLS], [SEP], Padding)
            labels.append(IGNORE_INDEX)
        elif word_id != previous_word:
            # erstes Subword eines Wortes -> trägt das Label
            labels.append(label2id[word_tags[word_id]])
        else:
            # Fortsetzungs-Subword -> maskieren
            labels.append(IGNORE_INDEX)
        previous_word = word_id
    return labels
