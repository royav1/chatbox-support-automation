from app.schemas.chat_models import Intent

def respond(intent: Intent) -> tuple[str, bool]:
    """
    Returns (reply, handoff_required)
    """

    if intent == "VPN_ISSUE":
        return (
            "VPN troubleshooting steps:\n"
            "1) Disconnect and reconnect VPN.\n"
            "2) Check your internet connection.\n"
            "3) Restart the VPN client.\n"
            "If you see an error code, paste it here.",
            False,
        )

    if intent == "PASSWORD_RESET":
        return (
            "Password reset help:\n"
            "1) Use the 'Forgot password' option.\n"
            "2) Confirm which system you’re trying to access.\n"
            "3) Tell me if you see any specific error message.",
            False,
        )

    if intent == "EMAIL_ISSUE":
        return (
            "Email issue troubleshooting:\n"
            "• Are you unable to send, receive, or both?\n"
            "• Which client are you using (Outlook, Gmail, web)?\n"
            "• What error message do you see?",
            False,
        )

    if intent == "GENERAL":
        return (
            "Please describe:\n"
            "• which system\n"
            "• what exactly happened\n"
            "• any error message\n"
            "and I’ll guide you.",
            False,
        )

    return (
        "I’m not sure I understood. Please rephrase your issue in one sentence.",
        False,
    )
