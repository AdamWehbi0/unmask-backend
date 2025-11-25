from supabase_client import get_supabase_client
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, messaging
import os

FCM_CREDENTIALS_PATH = os.getenv("FCM_CREDENTIALS_PATH")

if not FCM_CREDENTIALS_PATH or not os.path.exists(FCM_CREDENTIALS_PATH):
	raise ValueError("Firebase credentials not configured. Set FCM_CREDENTIALS_PATH environment variable to the path of your Firebase service account JSON file.")

if not firebase_admin._apps:
	creds = credentials.Certificate(FCM_CREDENTIALS_PATH)
	firebase_admin.initialize_app(creds)

async def send_notification(user_id: str, notification_type: str, title: str, body: str, data: dict = None):
	client = get_supabase_client()
	
	try:
		tokens = client.table("notification_tokens").select("device_token, platform").eq("user_id", user_id).is_("deleted_at", None).execute()
		
		notification_record = {
			"recipient_id": user_id,
			"notification_type": notification_type,
			"title": title,
			"body": body,
			"data": data or {},
			"is_sent": False
		}
		
		resp = client.table("notifications_sent").insert(notification_record).select().execute()
		notification_id = resp.data[0]["id"] if resp.data else None
		
		for token_data in tokens.data:
			device_token = token_data["device_token"]
			platform = token_data["platform"]
			
			try:
				if platform == "android":
					message = messaging.Message(
						notification=messaging.Notification(
							title=title,
							body=body
						),
						data=data or {},
						token=device_token
					)
					messaging.send(message)
				elif platform == "ios":
					message = messaging.Message(
						notification=messaging.Notification(
							title=title,
							body=body
						),
						data=data or {},
						token=device_token,
						apns=messaging.APNSConfig(
							payload=messaging.APNSPayload(
								aps=messaging.Aps(
									alert=messaging.ApsAlert(
										title=title,
										body=body
									),
									sound='default'
								)
							)
						)
					)
					messaging.send(message)
				
				if notification_id:
					client.table("notifications_sent").update({
						"is_sent": True,
						"sent_at": datetime.utcnow().isoformat()
					}).eq("id", notification_id).execute()
			except Exception as e:
				print(f"Error sending notification to {device_token}: {e}")
	except Exception as e:
		print(f"Error in send_notification: {e}")

async def notify_new_match(user_id: str, match_with_name: str):
	await send_notification(
		user_id,
		"new_match",
		"New Match!",
		f"You matched with {match_with_name}!",
		{"type": "match", "action": "open_matches"}
	)

async def notify_new_message(user_id: str, sender_name: str, message_preview: str):
	await send_notification(
		user_id,
		"new_message",
		f"Message from {sender_name}",
		message_preview[:100],
		{"type": "message", "action": "open_chat"}
	)

async def notify_super_like(user_id: str, liker_name: str):
	await send_notification(
		user_id,
		"super_like",
		f"💙 {liker_name} Super Liked You!",
		"See who super liked you",
		{"type": "super_like", "action": "open_likes"}
	)
