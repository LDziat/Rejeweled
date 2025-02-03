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
        self.room_name = 'game_room'  # You can use dynamic names if needed
        self.room_group_name = f'game_{self.room_name}'  # Group name for broadcasting

        # Join the room group (this enables broadcasting to all connected clients)
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Accept the WebSocket connection first
        await self.accept()

        # Initialize the board for this consumer
        self.board = await self.generate_board()

        # Send the current board state to the new connection
        await self.send_board()

    async def disconnect(self, close_code):
        # Leave the room group when a user disconnects
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Receive message from WebSocket
        data = json.loads(text_data)
        x1, y1, x2, y2 = int(data["x1"]), int(data["y1"]), int(data["x2"]), int(data["y2"])

        if self.is_valid_swap(x1, y1, x2, y2):
            self.swap_gems(x1, y1, x2, y2)
            self.clear_matches()
            await self.animate_gravity()  # Step-by-step cascade animation
            # After updating, broadcast the new board state to all connected users
            await self.send_board_to_group()

    @sync_to_async
    def generate_board(self):
        """Loads the board state from the database or generates a new one if none exists."""
        game_board_id = uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')  # Replace with dynamic UUID or a fixed one
        game_board, created = GameBoard.objects.get_or_create(id=game_board_id)
        if created or not game_board.board_state:  # Initialize if newly created or empty
            game_board.board_state = [[random.choice(GEM_TYPES) for _ in range(8)] for _ in range(8)]
            game_board.save()

        return game_board.board_state

    def is_valid_swap(self, x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2) == 1  # Ensure it's a direct neighbor swap

    def swap_gems(self, x1, y1, x2, y2):
        x1 = int(x1)
        y1 = int(y1)
        x2 = int(x2)
        y2 = int(y2)
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
            self.board[y][x] = None  # Set matched gems to None (empty)

    async def animate_gravity(self, speed = 0.15):
        falling = True
        while falling:
            falling = False  # Assume everything is settled unless a move happens
            for y in range(6, -1, -1):  # Start from second-to-last row
                for x in range(8):
                    if self.board[y][x] and self.board[y + 1][x] is None:
                        self.board[y + 1][x] = self.board[y][x]
                        self.board[y][x] = None
                        falling = True  # Keep looping if a move happened
            await self.send_board()
            await self.send_board_to_group()
            await asyncio.sleep(speed)  # Pause to let animation catch up
        self.clear_matches()
        # Fill new gems at the top
        recurse_flag = False
        for x in range(8):
            if self.board[0][x] is None:
                self.board[0][x] = random.choice(GEM_TYPES)
                recurse_flag = True
        if recurse_flag:
            await self.animate_gravity(speed=speed/1.2)

        await self.send_board()  # Final board state after cascade
        await self.send_board_to_group()

    @sync_to_async
    def save_board_to_db(self):
        # Save the current board state back to the database
        game_board_id = uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
        game_board = GameBoard.objects.get(id=game_board_id)
        game_board.board_state = self.board
        game_board.save()

    async def send_board(self, event=None):
        """ Sends the board state to WebSocket, event argument is optional (for group sends). """
        if event:
            board = event['board']  # If event is passed (from group send), use the board from there
        else:
            board = self.board  # Else, use the local board state
        await self.save_board_to_db()
        await self.send(text_data=json.dumps({"board": board}))

    async def send_board_to_group(self):
        """ Sends the board state to all connected clients using group send """
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'send_board',  # This will trigger the send_board method with event
                'board': self.board
            }
        )


    async def send_board_to_websocket(self, event):
        # This will be triggered when a message is sent to the group
        await self.send(text_data=json.dumps({"board": event['board']}))
