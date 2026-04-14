class PDFGenerationService:
    """Placeholder for SR PDF generation.

    PDF generation is planned for Phase 2. Until then, calls to ``generate``
    will raise :class:`NotImplementedError`. Tests patch this class directly,
    so unit tests continue to pass without a real implementation.
    """

    async def generate(self, sr_type: str, answers: dict) -> bytes:
        """Generate a PDF for an SR submission.

        Not yet implemented — PDF generation is planned for Phase 2.
        """
        raise NotImplementedError("PDF generation planned for Phase 2")
