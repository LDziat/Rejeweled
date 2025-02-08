from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from .models import GameBoard, GamePlayer
from django.contrib.auth.models import User
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
        self.score = 0
        self.combo_multiplier = 1.0

        self.user = self.scope["user"]
        print(self.user)
        if self.user.is_authenticated:
            self.game_player = await self.get_or_create_game_player()
            self.score = await self.get_player_score()
        else:
            self.score = 0
        
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        self.board = await self.get_board_from_db()
        await self.send_board()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        x1, y1, x2, y2 = int(data["x1"]), int(data["y1"]), int(data["x2"]), int(data["y2"])
        
        board_lock = asyncio.Lock()
        async with board_lock:
            self.board = await self.get_board_from_db()
            
            if self.is_valid_swap(x1, y1, x2, y2):
                self.swap_gems(x1, y1, x2, y2)
                if not self.has_valid_moves():
                    await self.shuffle_board()
                matches = self.find_matches()
                if matches:
                    await self.process_matches()
                    await self.save_board_to_db()
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'broadcast_move',
                            'board': self.board,
                            'player_id': self.player_id,
                            'score': self.score
                        }
                    )
                else:
                    self.swap_gems(x1, y1, x2, y2)  # Swap back if no matches
                    await self.send_board()

    def find_matches(self):
        matched = set()
        
        # Check horizontal matches
        for y in range(8):
            for x in range(6):
                if self.board[y][x] and self.board[y][x] == self.board[y][x + 1] == self.board[y][x + 2]:
                    matched |= {(y, x), (y, x + 1), (y, x + 2)}
        
        # Check vertical matches
        for y in range(6):
            for x in range(8):
                if self.board[y][x] and self.board[y][x] == self.board[y + 1][x] == self.board[y + 2][x]:
                    matched |= {(y, x), (y + 1, x), (y + 2, x)}
        
        return matched

    @database_sync_to_async
    def get_player_score(self):
        return self.game_player.score

    @database_sync_to_async
    def update_player_score(self, points):
        self.game_player.update_score(points)
        self.game_player.save()  # Make sure to save the changes
        return self.game_player.score

    @database_sync_to_async
    def get_or_create_game_player(self):
        game_player, created = GamePlayer.objects.get_or_create(user=self.user)
        return game_player


    async def update_score(self, matches):
        if not self.user.is_authenticated:
            return 0
            
        points_per_gem = 10
        size_multiplier = 1.0
        if len(matches) > 3:
            size_multiplier = 1.5
        if len(matches) > 4:
            size_multiplier = 2.0
            
        points = int(len(matches) * points_per_gem * size_multiplier * self.combo_multiplier)
        
        # Update score in database
        self.score = await self.update_player_score(points)
        return points


    def clear_matches(self, matches):
        if not matches:
            return False
        
        for y, x in matches:
            self.board[y][x] = None

        return True  # Removed score update from here as it's now handled in update_score


    def has_valid_moves(self):
        # Checks if any valid swap exists that results in a match.
        for y in range(8):
            for x in range(8):
                # Try swapping right
                if x < 7:
                    self.swap_gems(x, y, x + 1, y)
                    if self.find_matches():
                        self.swap_gems(x, y, x + 1, y)  # Swap back
                        return True
                    self.swap_gems(x, y, x + 1, y)  # Swap back
                
                # Try swapping down
                if y < 7:
                    self.swap_gems(x, y, x, y + 1)
                    if self.find_matches():
                        self.swap_gems(x, y, x, y + 1)  # Swap back
                        return True
                    self.swap_gems(x, y, x, y + 1)  # Swap back

        return False  # No valid moves left

    async def shuffle_board(self):
        # Shuffles the board while ensuring at least one valid move exists.
        while True:
            # Generate a new random board
            self.board = [[random.choice(GEM_TYPES) for _ in range(8)] for _ in range(8)]

            # Ensure the shuffled board has at least one valid move
            if self.has_valid_moves():
                break  # Exit loop when a playable board is found

        await self.save_board_to_db()
        await self.send_board_to_group()


    async def process_matches(self, is_combo=False):
        matches = self.find_matches()
        if not matches:
            return False
        
        if not is_combo:
            self.combo_multiplier = 1.0
        
        # Calculate and update score
        points = await self.update_score(matches)
        self.score = await self.get_player_score()  # Update local score after DB update
        
        self.clear_matches(matches)
        await self.animate_gravity()
        
        new_matches = self.find_matches()
        if new_matches:
            self.combo_multiplier += 0.5
            await self.process_matches(is_combo=True)
        
        return True

    async def animate_gravity(self, speed=0.15, max_depth=40):
        falling = True
        if max_depth <= 0:
            return  # Avoid infinite recursion by stopping after max_depth.
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

        need_refill = False
        for x in range(8):
            if self.board[0][x] is None:
                self.board[0][x] = random.choice(GEM_TYPES)
                need_refill = True
        
        if need_refill:
            await self.animate_gravity(speed=speed/1.2, max_depth=max_depth-1)

        matches = self.find_matches()
        if not self.has_valid_moves():
            await self.shuffle_board()

        print(matches)
        if matches:
            print("Clearing")
            self.clear_matches(matches)
            await self.animate_gravity(speed=speed/1.2, max_depth=max_depth-1)

    def is_valid_swap(self, x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2) == 1

    def swap_gems(self, x1, y1, x2, y2):
        self.board[y1][x1], self.board[y2][x2] = self.board[y2][x2], self.board[y1][x1]

    @sync_to_async
    def get_board_from_db(self):
        game_board_id = uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
        game_board, created = GameBoard.objects.get_or_create(id=game_board_id)
        if created or not game_board.board_state:
            game_board.board_state = [[random.choice(GEM_TYPES) for _ in range(8)] for _ in range(8)]
            game_board.save()
        return game_board.board_state

    @sync_to_async
    def save_board_to_db(self):
        game_board_id = uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
        game_board = GameBoard.objects.get(id=game_board_id)
        game_board.board_state = self.board
        game_board.save()

    @database_sync_to_async
    def get_score_from_db(self):
        game_board = GameBoard.objects.get(id=uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479'))
        return game_board.score or 0

    @database_sync_to_async
    def save_score_to_db(self):
        game_board = GameBoard.objects.get(id=uuid.UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479'))
        game_board.score = self.score
        game_board.save()

    async def send_board(self):
        await self.send(text_data=json.dumps({
            "board": self.board,
            "player_id": self.player_id,
            "score": self.score
        }))

    async def send_board_to_group(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'broadcast_move',
                'board': self.board,
                'player_id': self.player_id,
                
            }
        )

    async def broadcast_move(self, event):
        if event['player_id'] != self.player_id:
            await self.send(text_data=json.dumps({
                "board": event['board'],
                "player_id": event['player_id'],
            }))
