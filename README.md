# Nesta DAPS

A non-project specific DAPS for Nesta.

**🚧 This repo is under construction 🚧**

- [Repository structure](#explanation-of-repository-structure)
- [Contribution etiquette](#contribution-etiquette)

## Explanation of repository structure

The structure of this repo is provided below.

```
nesta_daps
├── VERSION	                       | Automatically kept up-to-date by hooks

├── common                         | Any utils to be pooled across flows.
│	├── ...						   | If these need to be imported into other
│   │   ├── something.py		   | repos then they should be factored into
│   │   ├── requirements.txt	   | nestauk/data_utils
│   │   └── tests				   |
│   │       └── test_something.py  |

│   └── requirements.txt		   | Note that requirements should be factored
								   | out as much as possible and recombined
								   | at the flow level to avoid clashes.

├── deploy						   | Flows are orchestrated by tasks,
│   ├── Dockerfile				   | which are deployed and orchestrated
│   └── terraform				   | by AWS EventBridge
│       └── module.tf			   |

├── flows						   | Flows are split into "datasets" and "projects",
								   | where "projects" are project-specific
								   | implementations of one or more "datasets".
								   |
								   | Unambiguously, all raw data should be collected
								   | in under the "datasets" flows. If a dataset needs
								   | to be enriched, the enrichment could go under
								   | either "projects" or "datasets", although
								   | where those features might generally be
								   | considered useful to multiple "projects" then
								   | then enrichment should go under "datasets"
│   ├── datasets
│   │   └── gtr					   | An example of a dataset which cuts across "projects"
│   │       ├── gtr_flow.py		   |
│   │       ├── gtr_utils.py	   |
│   │       ├── requirements.txt   |
│   │       └── tests			   |
│   │           └── test_gtr.py	   |

│   └── projects				   | Examples of some "projects" which might aggregate
│       ├── discovery			   | data from "datasets"
│       │   └── requirements.txt   |
│       ├── fairer_start		   |
│       │   └── requirements.txt   |
│       ├── healthy_life		   |
│       │   └── requirements.txt   |
│       └── sustainable_future	   |
│           └── requirements.txt   |

├── requirements.txt			   | Very low level requirements that are core to all
                                   | flows and tasks.

└── tasks						   | Tasks are grouped by time period, and should
    ├── daily.py				   | execute curate tasks.
    ├── monthly.py				   |
    └── weekly.py				   |
```

## Contribution etiquette

After cloning the repo, you will need to run `bash install.sh` from the repository root. This will setup
automatic calendar versioning for you, and also some checks on your working branch name. For avoidance of doubt,
branches must be linked to a GitHub issue and named accordingly:

```bash
{GitHub issue number}_{tinyLowerCamelDescription}
```

For example `14_readme`, which indicates that [this branch](https://github.com/nestauk/ojd_daps/pull/24) refered to [this issue](https://github.com/nestauk/ojd_daps/issues/14).

The remote repo anyway forbids you from pushing directly to the `dev` branch, and the local repo will forbid you from committing to either `dev` or `master`, and so you only pull requests from branches named `{GitHub issue number}_{tinyLowerCamelDescription}` will be accepted.

Please make all PRs and issues reasonably small: they should be trying to achieve roughly one task. Inevitably some simple tasks spawn large numbers of utils, and sometimes these detract from the original PR. In this case, you should stack an new PR on top of your "base" PR, for example as `{GitHub issue number}_{differentLowerCamelDescription}`. In this case the PR / Git merging tree will look like:

    dev <-- 123_originalThing <-- 423_differentThing <-- 578_anotherDifferentThing

We can then merge the PR `123_originalThing` into `dev`, then `423_differentThing` into `dev` (after calling `git merge dev` on `423_differentThing`), etc until the chain is merged entirely. The nominated reviewer should review the entire chain, before the merge can go ahead. PRs should only be merged if all tests and a review has been signed off.
