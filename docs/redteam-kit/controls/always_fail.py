import json, sys
print(json.dumps({"implementer": "control/always-fail", "result": "FAIL",
                  "checks": [{"id": "S11", "result": "FAIL"}]}))
sys.exit(1)
