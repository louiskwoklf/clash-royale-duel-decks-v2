import requests
from flask import Flask, render_template, request
from bs4 import BeautifulSoup
import os
import json

app = Flask(__name__)

def fetch_html(url):
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/91.0.4472.124 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text  # 'requests' handles decompression automatically
    else:
        print(f"Error fetching page: {response.status_code}")
        return None

def extract_decks(html_content):
    soup = BeautifulSoup(html_content, "lxml")
    deck_segments = soup.find_all('div', class_='ui attached segment deck_segment')
    decks = []
    unique_deck_cards = set()  # To keep track of unique card combinations

    for deck_segment in deck_segments:
        # Extract the deck name
        deck_name_tag = deck_segment.find('h4', class_='deck_human_name-mobile')
        if deck_name_tag:
            deck_name = deck_name_tag.get_text(strip=True)
        else:
            deck_name = 'Unknown Deck Name'

        # Extract the card names
        card_names = []
        card_img_tags = deck_segment.find_all('img', class_='deck_card')
        for img_tag in card_img_tags:
            # Use 'data-card-key' attribute to get the card key
            card_key = img_tag.get('data-card-key')
            if card_key:
                card_names.append(card_key)
            else:
                # Fallback to 'alt' attribute if 'data-card-key' is missing
                card_alt = img_tag.get('alt')
                if card_alt:
                    card_name = card_alt.lower().replace(' ', '-')
                    card_names.append(card_name)

        # Sort the card names to ensure consistent ordering for comparison
        card_names_sorted = sorted(card_names)

        # Create a tuple of the sorted card names to use as a set key
        card_names_tuple = tuple(card_names_sorted)

        # Check if this combination of cards has already been added
        if card_names_tuple not in unique_deck_cards:
            # Add the combination to the set of unique decks
            unique_deck_cards.add(card_names_tuple)
            # Store the deck information
            decks.append({
                'deck_name': deck_name,
                'cards': card_names
            })
        else:
            # Duplicate deck found; skip adding it
            print(f"Duplicate deck found and skipped: {deck_name}")

    return decks

def find_duel_decks(decks):
    from itertools import combinations

    valid_duel_decks = []

    # Generate all possible combinations of 4 decks
    for duel_deck in combinations(decks, 4):
        # Collect all card names in the duel deck
        all_cards = [card for deck in duel_deck for card in deck['cards']]
        all_cards_cleaned = [card.removesuffix("-ev1") for card in all_cards]
        # Check if there are any duplicate cards
        if len(all_cards_cleaned) == len(set(all_cards_cleaned)):
            # No duplicates, add to valid duel decks
            valid_duel_decks.append({'decks': duel_deck})

    return valid_duel_decks

def get_card_image(card_name):
    # Define the local image path
    image_folder = os.path.join(app.static_folder, 'cards')
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
    local_image_path = os.path.join(image_folder, f'{card_name}.png')

    # Check if the image already exists
    if not os.path.exists(local_image_path):
        # Image doesn't exist locally; download it
        # Construct the image URL based on the card name
        image_url = f'https://cdn.royaleapi.com/static/img/cards/{card_name}.png'
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://royaleapi.com/"
        }
        print(f'Attempting to download image for {card_name} from {image_url}')
        response = requests.get(image_url, headers=headers)
        if response.status_code == 200:
            # Save the image to the local file system
            with open(local_image_path, 'wb') as f:
                f.write(response.content)
            print(f'Downloaded image for {card_name}')
        else:
            print(f'Failed to download image for {card_name}')
            print(f'HTTP status code: {response.status_code}')
            print(f'Attempted URL: {image_url}')
    else:
        print(f'Image for {card_name} already exists locally')

def ensure_card_images(decks):
    for deck in decks:
        for card in deck['cards']:
            get_card_image(card)

def load_game_modes(file_path='game_modes.json'):
    if not os.path.exists(file_path):
        print(f"Game modes file '{file_path}' not found.")
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            game_modes = json.load(f)
            return game_modes
        except json.JSONDecodeError as e:
            print(f"Error parsing game modes file: {e}")
            return []

@app.route('/')
def index():
    game_modes = load_game_modes()
    game_mode_id = request.args.get('game_mode_id')
    selected_game_mode = None
    display_name = ''
    if game_mode_id:
        # Find the selected game mode by 'id'
        selected_game_mode = next((mode for mode in game_modes if mode['id'] == game_mode_id), None)
        if not selected_game_mode:
            # Invalid game mode selected
            return render_template('error.html', message='Invalid game mode selected.')
        
        # Fetch and process decks using the URL from the selected game mode
        html_content = fetch_html(selected_game_mode['url'])
        if html_content:
            decks = extract_decks(html_content)
            ensure_card_images(decks)
            valid_duel_decks = find_duel_decks(decks)
        else:
            decks = []
            valid_duel_decks = []
        
        display_name = selected_game_mode['display_name']
    else:
        # No game mode selected yet
        decks = []
        valid_duel_decks = []
    
    return render_template(
        'index.html',
        duel_decks=valid_duel_decks,
        game_modes=game_modes,
        selected_game_mode_id=game_mode_id,
        display_name=display_name
    )

if __name__ == '__main__':
    app.run(debug=True)