from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from datetime import datetime
from supabase_client import get_supabase_client
from app.auth import verify_token
from typing import Dict, Set

router = APIRouter(prefix="/matches", tags=["messages"])

class MessageCreate(BaseModel):
	content: str

active_connections: Dict[str, Set[WebSocket]] = {}

@router.get("/{match_id}/messages")
async def get_messages(
	match_id: str,
	limit: int = 50,
	offset: int = 0,
	user_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		match = client.table("matches").select("user1, user2").eq("id", match_id).single().execute()
		if user_id not in [match.data["user1"], match.data["user2"]]:
			raise HTTPException(status_code=403, detail="Unauthorized")
		
		resp = client.table("messages")\
			.select("*")\
			.eq("match_id", match_id)\
			.order("created_at", desc=True)\
			.limit(limit)\
			.offset(offset)\
			.execute()
		
		return resp.data
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.post("/{match_id}/messages")
async def send_message(
	match_id: str,
	msg: MessageCreate,
	user_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		match = client.table("matches").select("user1, user2, reveal_user1, reveal_user2").eq("id", match_id).single().execute()
		if user_id not in [match.data["user1"], match.data["user2"]]:
			raise HTTPException(status_code=403, detail="Unauthorized")
		
		if not (match.data["reveal_user1"] and match.data["reveal_user2"]):
			raise HTTPException(status_code=400, detail="Both users must reveal first")
		
		resp = client.table("messages").insert({
			"match_id": match_id,
			"sender_id": user_id,
			"content": msg.content
		}).select().execute()
		
		return resp.data[0]
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.websocket("/ws/{match_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str, user_id: str):
	await websocket.accept()
	client = get_supabase_client()
	
	try:
		match = client.table("matches").select("user1, user2").eq("id", match_id).single().execute()
		if user_id not in [match.data["user1"], match.data["user2"]]:
			await websocket.close(code=4003, reason="Unauthorized")
			return
		
		connection_key = f"{match_id}"
		
		if connection_key not in active_connections:
			active_connections[connection_key] = set()
		active_connections[connection_key].add(websocket)
		
		while True:
			data = await websocket.receive_json()
			content = data.get("content", "").strip()
			
			if not content:
				continue
			
			msg_resp = client.table("messages").insert({
				"match_id": match_id,
				"sender_id": user_id,
				"content": content
			}).select().execute()
			
			message_data = {
				"id": msg_resp.data[0]["id"],
				"sender_id": user_id,
				"content": content,
				"created_at": msg_resp.data[0]["created_at"],
				"type": "message"
			}
			
			for connection in active_connections[connection_key]:
				try:
					await connection.send_json(message_data)
				except Exception:
					pass
	
	except WebSocketDisconnect:
		if match_id in active_connections:
			active_connections[match_id].discard(websocket)
			if not active_connections[match_id]:
				del active_connections[match_id]
	
	except Exception as e:
		try:
			await websocket.close(code=1011, reason=str(e))
		except:
			pass

@router.post("/{match_id}/messages/{message_id}/read")
async def mark_message_read(
	match_id: str,
	message_id: str,
	user_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		match = client.table("matches").select("user1, user2").eq("id", match_id).single().execute()
		if user_id not in [match.data["user1"], match.data["user2"]]:
			raise HTTPException(status_code=403, detail="Unauthorized")
		
		message = client.table("messages").select("id, sender_id").eq("id", message_id).eq("match_id", match_id).single().execute()
		if not message.data:
			raise HTTPException(status_code=404, detail="Message not found")
		
		if message.data["sender_id"] == user_id:
			raise HTTPException(status_code=400, detail="Cannot mark own message as read")
		
		client.table("messages").update({
			"is_read": True,
			"read_at": datetime.utcnow().isoformat()
		}).eq("id", message_id).execute()
		
		return {"status": "marked_read"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/{match_id}/unread-count")
async def get_unread_count(
	match_id: str,
	user_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		match = client.table("matches").select("user1, user2").eq("id", match_id).single().execute()
		if user_id not in [match.data["user1"], match.data["user2"]]:
			raise HTTPException(status_code=403, detail="Unauthorized")
		
		unread = client.table("messages").select("id").eq("match_id", match_id).neq("sender_id", user_id).eq("is_read", False).execute()
		
		return {"unread_count": len(unread.data)}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
