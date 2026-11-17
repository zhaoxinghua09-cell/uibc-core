import sys
sys.path.insert(0, r"tools")
import open_pr as o

t, _ = o.pick_token()
st, d = o.call("%s/repos/%s/%s/pulls/66" % (o.API, o.OWNER, o.REPO), t)
print("PR66:", st, d.get("state"), d.get("merged"), d.get("mergeable_state"))
st, c = o.call("%s/repos/%s/%s/compare/main...release/v1.1-precheck" % (o.API, o.OWNER, o.REPO), t)
print("compare:", c.get("status"), "ahead", c.get("ahead_by"), "behind", c.get("behind_by"))
st, m = o.call("%s/repos/%s/%s/commits/main" % (o.API, o.OWNER, o.REPO), t)
print("main:", m["sha"], m["commit"]["message"].splitlines()[0][:60])
