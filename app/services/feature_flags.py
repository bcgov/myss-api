import os


class FeatureFlagService:
    @staticmethod
    def t5_disabled() -> bool:
        return os.getenv("FEATURE_T5_DISABLED", "false").lower() == "true"
