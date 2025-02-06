from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from .models import GameBoard
import uuid
import random
import json
from channels.layers import get_channel_layer
import asyncio

GEM_TYPES = ["red", "blue", "green", "yellow", "purple", "orange", "white"]

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = 'game_room'
        self.room_group_name = f'game_{self.room_name}'
        self.player_id = str(uuid.uuid4())
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        
        self.board = await self.get_board_from_db()
        await self.send_board()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        x1, y1, x2, y2 = int(data["x1"]), int(data["y1"]), int(data["x2"]), int(data["y2"])
        
        board_lock = asyncio.Lock()
        async with board_lock:
            self.board = await self.get_board_from_db()
            
            if self.is_valid_swap(x1, y1, x2, y2):
                self.swap_gems(x1, y1, x2, y2)
                if self.clear_matches():
                    await self.animate_gravity()
                    await self.save_board_to_db()
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'broadcast_move',
                            'board': self.board,
                            'player_id': self.player_id
                        }
                    )
                else:
                    self.swap_gems(x1, y1, x2, y2)
                    await self.send_board()

    @sync_to_async
    def get_board_from_db(self):
        game_board_id = uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
        game_board, created = GameBoard.objects.get_or_create(id=game_board_id)
        if created or not game_board.board_state:
            game_board.board_state = [[random.choice(GEM_TYPES) for _ in range(8)] for _ in range(8)]
            game_board.save()
        return game_board.board_state

    def is_valid_swap(self, x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2) == 1

    def swap_gems(self, x1, y1, x2, y2):
        self.board[y1][x1], self.board[y2][x2] = self.board[y2][x2], self.board[y1][x1]

    def clear_matches(self):
        matched = set()
        for y in range(8):
            for x in range(8):
                if x < 6 and self.board[y][x] == self.board[y][x + 1] == self.board[y][x + 2]:
                    matched |= {(y, x), (y, x + 1), (y, x + 2)}
                if y < 6 and self.board[y][x] == self.board[y + 1][x] == self.board[y + 2][x]:
                    matched |= {(y, x), (y + 1, x), (y + 2, x)}

        for y, x in matched:
            self.board[y][x] = None
        return len(matched) > 0

    async def animate_gravity(self, speed=0.15):
        falling = True
        while falling:
            falling = False
            for y in range(6, -1, -1):
                for x in range(8):
                    if self.board[y][x] and self.board[y + 1][x] is None:
                        self.board[y + 1][x] = self.board[y][x]
                        self.board[y][x] = None
                        falling = True
            await self.send_board()
            await self.send_board_to_group()
            await asyncio.sleep(speed)

        recurse_flag = False
        for x in range(8):
            if self.board[0][x] is None:
                self.board[0][x] = random.choice(GEM_TYPES)
                recurse_flag = True
        
        if recurse_flag:
            await self.animate_gravity(speed=speed/1.2)

        if self.clear_matches():
            await self.animate_gravity(speed=speed/1.2)

    @sync_to_async
    def save_board_to_db(self):
        game_board_id = uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
        game_board = GameBoard.objects.get(id=game_board_id)
        game_board.board_state = self.board
        game_board.save()

    async def send_board(self):
        await self.send(text_data=json.dumps({
            "board": self.board,
            "player_id": self.player_id
        }))

    async def send_board_to_group(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'broadcast_move',
                'board': self.board,
                'player_id': self.player_id
            }
        )

    async def broadcast_move(self, event):
        if event['player_id'] != self.player_id:
            await self.send(text_data=json.dumps({
                "board": event['board'],
                "player_id": event['player_id']
            }))