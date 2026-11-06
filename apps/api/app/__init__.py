"""Labor Case Agent API."""

from pathlib import Path

from dotenv import load_dotenv


# Load the repository-level local configuration without overriding explicit
# process variables used by tests, containers, and deployment environments.
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
