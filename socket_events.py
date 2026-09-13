"""Socket.io server for GlintMesh real-time events and animations."""

import socketio
import asyncio
import json
from datetime import datetime

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

connected_users = {}


@sio.event
async def connect(sid, environ):
    connected_users[sid] = {
        'connected_at': datetime.utcnow().isoformat(),
        'rooms': set()
    }
    await sio.emit('connected', {
        'sid': sid,
        'message': 'Connected to GlintMesh real-time',
        'users_count': len(connected_users),
        'timestamp': datetime.utcnow().isoformat()
    }, room=sid)


@sio.event
async def disconnect(sid):
    if sid in connected_users:
        del connected_users[sid]
    await sio.emit('user_left', {
        'users_count': len(connected_users),
        'timestamp': datetime.utcnow().isoformat()
    })


@sio.event
async def join_room(sid, data):
    room = data.get('room', 'general')
    await sio.enter_room(sid, room)
    if sid in connected_users:
        connected_users[sid]['rooms'].add(room)
    await sio.emit('room_joined', {
        'room': room,
        'message': f'Joined room: {room}'
    }, room=sid)


@sio.event
async def leave_room(sid, data):
    room = data.get('room', 'general')
    await sio.leave_room(sid, room)
    if sid in connected_users:
        connected_users[sid]['rooms'].discard(room)


async def emit_generation_start(request_data):
    """Emit when a new interface generation starts."""
    await sio.emit('generation_start', {
        'message': request_data.get('message', ''),
        'timestamp': datetime.utcnow().isoformat(),
        'mode': request_data.get('mode', 'full')
    })


async def emit_tool_call(tool_name, args):
    """Emit when an MCP tool is called."""
    await sio.emit('tool_call', {
        'tool': tool_name,
        'args': args,
        'timestamp': datetime.utcnow().isoformat(),
        'animation': 'pulse'
    })


async def emit_tool_result(tool_name, data, failed=False):
    """Emit when an MCP tool returns results."""
    await sio.emit('tool_result', {
        'tool': tool_name,
        'data': data,
        'failed': failed,
        'timestamp': datetime.utcnow().isoformat(),
        'animation': 'glow' if not failed else 'shake'
    })


async def emit_a2ui_update(surface_type, data):
    """Emit A2UI surface data for real-time rendering."""
    await sio.emit('a2ui_update', {
        'surface_type': surface_type,
        'data': data,
        'timestamp': datetime.utcnow().isoformat(),
        'animation': 'slideIn'
    })


async def emit_price_update(symbol, price, change):
    """Emit real-time price updates for animated tickers."""
    await sio.emit('price_update', {
        'symbol': symbol,
        'price': price,
        'change': change,
        'timestamp': datetime.utcnow().isoformat()
    })


async def emit_generation_complete(html, summary=''):
    """Emit when generation is complete."""
    await sio.emit('generation_complete', {
        'html': html[:500] if html else '',
        'summary': summary,
        'timestamp': datetime.utcnow().isoformat(),
        'animation': 'celebrate'
    })


async def emit_generation_error(error_msg):
    """Emit on generation error."""
    await sio.emit('generation_error', {
        'message': error_msg,
        'timestamp': datetime.utcnow().isoformat(),
        'animation': 'shake'
    })


async def broadcast_data_refresh(dataset_info):
    """Broadcast data refresh to all connected clients."""
    await sio.emit('data_refresh', {
        'dataset': dataset_info,
        'timestamp': datetime.utcnow().isoformat(),
        'animation': 'fadeIn'
    })


def get_users_count():
    return len(connected_users)
