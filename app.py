import os
from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO, emit
import random
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hangmansecret'
socketio = SocketIO(app, async_mode='eventlet')

HANGMANPICS = ['''
  +---+
  |   |
      |
      |
      |
      |
=========''', '''
  +---+
  |   |
  O   |
      |
      |
      |
=========''', '''
  +---+
  |   |
  O   |
  |   |
      |
      |
=========''', '''
  +---+
  |   |
  O   |
 /|   |
      |
      |
=========''', '''
  +---+
  |   |
  O   |
 /|\  |
      |
      |
=========''', '''
  +---+
  |   |
  O   |
 /|\  |
 /    |
      |
=========''', '''
  +---+
  |   |
  O   |
 /|\  |
 / \  |
      |
=========''', '''
  +---+
  |   |
 [O]  |
 /|\  |
 / \  |
      |
=========''']

players = []
player_sids = {}
host = None
game_lock = threading.Lock()
game_state = {
    'word': '',
    'display_word': '',
    'wrong_letters': [],
    'lives': 7,
    'turn_index': 0,
    'turn': '',
    'game_over': False,
    'winner': None
}

def choose_word():
    return random.choice(["absorb", "archive", "biscuit", "blister", "cactus", "capture", "cascade", "chamber", "charter", "clarity", "climax", "conduct", "crumble", "custody", "dazzled", "delight", "dignity", "diploma", "disrupt", "dynamic", "elastic", "elevate", "emerald", "enigma", "escort", "exhibit", "expense", "factual", "failure", "fantasy", "fervent", "fiasco", "flutter", "frantic", "furnace", "gadget", "gallant", "garnish", "glisten", "grumble", "ignite", "illness", "impulse", "inquire", "insight", "intense", "journey", "justice", "kingdom", "lantern", "leisure", "lecture", "license", "linger", "luggage", "luxury", "loyalty", "lawful", "launch", "lattice", "magnet", "mascot", "mature", "maximum", "meadow", "meddle", "melody", "message", "midnight", "minimum", "mission", "monitor", "morally", "mystery", "nurture", "obscure", "opinion", "outlaw", "outwit", "overlap", "package", "parade", "patient", "pattern", "perfect", "phrase", "pioneer", "pirate", "plastic", "plummet", "precise", "preserve", "profile", "project", "propel", "pursuit", "quicken", "radiate", "recruit", "reflect", "reform", "relieve", "remorse", "rescue", "resolve", "rigidly", "rotate", "rustic", "saffron", "sample", "tactics", "talent", "tangle", "target", "texture", "theater", "thrive", "thunder", "tolerate", "torrent", "transit", "treason", "triumph", "trouble", "tunnel", "uncover", "unravel", "upright", "useful", "utmost", "vacuum", "venture", "verdict", "vessel", "victory", "vulture", "wander", "warrior", "wealthy", "witness", "wonder", "wooden", "worsen", "wrinkle", "zealous", "zenith", "zodiac", "zombie", "zipper", "zinger"]
).lower()

def reset_game():
    with game_lock:
        game_state['word'] = choose_word()
        game_state['display_word'] = '_' * len(game_state['word'])
        game_state['wrong_letters'] = []
        game_state['lives'] = 7
        game_state['turn_index'] = 0
        game_state['turn'] = players[0] if players else ''
        game_state['game_over'] = False
        game_state['winner'] = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/game')
def game():
    name = request.args.get('name')
    if not name:
        return redirect('/')

    global host
    # ✅ Ensure host is set if not already
    if not host:
        host = name

    is_host = (host == name)
    return render_template('game.html', name=name, host=is_host)

@socketio.on('join')
def on_join(data):
    name = data['name']
    sid = request.sid
    global host

    if name not in players:
        players.append(name)
        player_sids[sid] = name

    # ✅ Assign host only if not already set
    if not host:
        host = name

    emit('player_list', {'players': players, 'host': host}, broadcast=True)

@socketio.on('start_game')
def on_start_game(data):
    if data['name'] != host:
        return
    reset_game()
    socketio.emit('game_started', get_game_data())

@socketio.on('guess')
def on_guess(data):
    letter = data['letter'].lower()
    name = data['name']
    with game_lock:
        if game_state['game_over'] or name != game_state['turn']:
            return
        if letter in game_state['word']:
            game_state['display_word'] = ''.join([
                letter if game_state['word'][i] == letter else game_state['display_word'][i]
                for i in range(len(game_state['word']))
            ])
        else:
            if letter not in game_state['wrong_letters']:
                game_state['wrong_letters'].append(letter)
                game_state['lives'] -= 1

        if game_state['display_word'] == game_state['word']:
            game_state['game_over'] = True
            game_state['winner'] = name
        elif game_state['lives'] <= 0:
            game_state['game_over'] = True
        else:
            game_state['turn_index'] = (game_state['turn_index'] + 1) % len(players)
            game_state['turn'] = players[game_state['turn_index']]

        emit('update_game', get_game_data(), broadcast=True)

@socketio.on('reset_game')
def on_reset_game(data):
    if data['name'] == host:
        reset_game()
        socketio.emit('game_reset', get_game_data())

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    name = player_sids.get(sid)
    global host

    if name and name in players:
        idx = players.index(name)
        players.remove(name)
        del player_sids[sid]

        # ✅ Safely reassign host
        if name == host:
            host = players[0] if players else None

        if players:
            game_state['turn_index'] %= len(players)
            game_state['turn'] = players[game_state['turn_index']]

        socketio.emit('player_list', {'players': players, 'host': host}, broadcast=True)

def get_game_data():
    return {
        'display_word': game_state['display_word'],
        'wrong_letters': game_state['wrong_letters'],
        'lives': game_state['lives'],
        'turn': game_state['turn'],
        'game_over': game_state['game_over'],
        'word': game_state['word'] if game_state['game_over'] else '',
        'winner': game_state['winner'],
        'hangman_ascii': HANGMANPICS[7 - game_state['lives']]
    }

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
