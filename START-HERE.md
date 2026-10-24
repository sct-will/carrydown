# Start here

## See it in 60 seconds

No agent, no token and no install. Clone the main repository and the sample repository side by side, then run three read-only commands on the sample. They print the schedule, the load table and the critical path, then the issues and the board the plan would create, without calling GitHub.

```bash
git clone https://github.com/sct-will/carrydown.git
git clone https://github.com/sct-will/carrydown-sample.git
cd carrydown
python3 scripts/check_specs.py --root ../carrydown-sample --report
python3 scripts/github_sync.py --root ../carrydown-sample --offline
python3 scripts/github_project.py --root ../carrydown-sample --offline
```

Measured on a laptop: the two clones took about 2 seconds, and each command about a fifth of a second. You need git and Python 3.9 or later.

## Then

1. Follow **Getting started** in the [README](README.md#getting-started). It has the install line and the three sentences to say to your agent.
2. Read the [plan owner guide](docs/plan-owner-guide.md) for the interview, the plan review, the token and the rhythm after the plan is on GitHub.
3. Open the [sample output](https://github.com/sct-will/carrydown-sample#readme) for the renderings, the live issues and the public board.
4. For the reasoning behind the steps, read [the method](docs/method.md). What changed recently is in the [changelog](CHANGELOG.md).
