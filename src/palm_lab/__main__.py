"""Allow `python -m palm_lab`, which is what shortcuts made from source run."""

from palm_lab.cli import main

raise SystemExit(main())
