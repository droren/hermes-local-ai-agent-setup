Summarize the following engineering note in at most 3 short bullet points. Preserve concrete constraints and do not add new facts.

Engineering note:
The Hermes Next local AI host has 48 GB unified memory. Models stored on the UNAS Pro must not be loaded directly over the network because model startup latency is too high. A selected cold model must first be staged to the Mac Mini Pro local SSD. External models are escalation-only and should not be selected merely because they are stronger. The scheduler should prefer already-local models when quality is close enough.
