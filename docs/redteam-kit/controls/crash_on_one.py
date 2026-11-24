import json, sys, os
if "not-json" in sys.argv[-1]:
    sys.stderr.write("Traceback (most recent call last):\nValueError: boom\n")
    sys.exit(9)
ids = ["S1","S2","S3","S4","S5","S6","S8","S11"]
print(json.dumps({"implementer": "control/crash-on-one", "result": "FAIL",
                  "checks": [{"id": i, "result": "FAIL"} for i in ids]}))
sys.exit(1)
