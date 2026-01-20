import os
import lark_oapi as lark

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def on_permission_applied(data: lark.drive.v1.P2DriveFilePermissionMemberAppliedV1) -> None:
    print(f"[drive.file.permission_member_applied_v1] {lark.JSON.marshal(data, indent=4)}")


def on_file_edit(data: lark.drive.v1.P2DriveFileEditV1) -> None:
    print(f"[drive.file.edit_v1] {lark.JSON.marshal(data, indent=4)}")


verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")

event_handler = lark.EventDispatcherHandler.builder(verification_token, encrypt_key) \
    .register_p2_drive_file_permission_member_applied_v1(on_permission_applied) \
    .register_p2_drive_file_edit_v1(on_file_edit) \
    .build()


def main():
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise ValueError("缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET，请先配置环境变量")

    cli = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    cli.start()


if __name__ == "__main__":
    main()