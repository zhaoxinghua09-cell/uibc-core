# P-01 starter kit (generic — parameterized variants are issued per agent)

Minimal path (30 seconds to a verifiable package):

    python -m uibc_core.cli demo            # see the whole lifecycle once
    uibc init my-agent.uibc
    uibc register my-agent.uibc --agent-id <your-agent-id> --owner <your-name>
    uibc evidence my-agent.uibc --type ACTION --file <evidence-file> --note "<what happened>"
    uibc keygen --out owner.key
    uibc submit my-agent.uibc --key owner.key
    uibc verify my-agent.uibc --key owner.key   # must print PASS / exit 0

Then submit per ../SUBMISSION.md. Your evidence file must describe real
actions you took; fabricated evidence is exactly what the gate exists to
catch.
