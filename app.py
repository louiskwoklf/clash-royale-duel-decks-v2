import requests
from flask import Flask, render_template, request, session, redirect, url_for
from bs4 import BeautifulSoup
import os
from itertools import combinations

app = Flask(__name__)

with open(os.path.join(app.static_folder, 'secret_key.txt'), 'r') as f:
    app.secret_key = f.read().strip()

DECKS_URL = "https://royaleapi.com/decks/popular?time=7d&sort=pop&size=30&players=PvP&min_trophies=0&max_trophies=9000&min_ranked_trophies=0&max_ranked_trophies=4000&min_elixir=1&max_elixir=9&evo=2&min_cycle_elixir=4&max_cycle_elixir=28&mode=detail&type=TopRanked&&&global_exclude=false"


def fetch_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Error fetching page: {response.status_code}")
        return None


def extract_decks(html_content):
    soup = BeautifulSoup(html_content, "lxml")
    deck_segments = soup.find_all('div', class_='ui attached segment deck_segment')
    decks = []
    unique_deck_cards = set()

    for deck_segment in deck_segments:
        deck_name_tag = deck_segment.find('h4', class_='deck_human_name-mobile')
        if deck_name_tag:
            deck_name = deck_name_tag.get_text(strip=True)
        else:
            deck_name = 'Unknown Deck Name'

        card_names = []
        card_img_tags = deck_segment.find_all('img', class_='deck_card')
        for img_tag in card_img_tags:
            card_key = img_tag.get('data-card-key')
            if card_key:
                card_names.append(card_key)
            else:
                card_alt = img_tag.get('alt')
                if card_alt:
                    card_name = card_alt.lower().replace(' ', '-')
                    card_names.append(card_name)

        card_names_sorted = sorted(card_names)
        card_names_tuple = tuple(card_names_sorted)

        if card_names_tuple not in unique_deck_cards:
            unique_deck_cards.add(card_names_tuple)
            decks.append({
                'deck_name': deck_name,
                'cards': card_names
            })
        else:
            print(f"Duplicate deck found and skipped: {deck_name}")

    return decks


def find_duel_decks(decks, allowed_repeated_cards):
    """
    Create duel decks (combinations of 4 decks) that satisfy the allowed duplicate rule.
    A duel deck is valid if the total number of duplicate cards (total cards minus unique cards)
    is less than or equal to allowed_repeated_cards.
    """
    valid_duel_decks = []
    for duel_deck in combinations(decks, 4):
        all_cards = [card for deck in duel_deck for card in deck['cards']]
        all_cards_cleaned = [card.removesuffix("-ev1") for card in all_cards]
        duplicate_count = len(all_cards_cleaned) - len(set(all_cards_cleaned))
        if duplicate_count <= allowed_repeated_cards:
            valid_duel_decks.append({'decks': duel_deck})
    return valid_duel_decks


def get_card_image(card_name):
    image_folder = os.path.join(app.static_folder, 'cards')
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
    local_image_path = os.path.join(image_folder, f'{card_name}.png')

    if not os.path.exists(local_image_path):
        image_url = f'https://cdn.royaleapi.com/static/img/cards/{card_name}.png'
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://royaleapi.com/"
        }
        print(f'Attempting to download image for {card_name} from {image_url}')
        response = requests.get(image_url, headers=headers)
        if response.status_code == 200:
            with open(local_image_path, 'wb') as f:
                f.write(response.content)
            print(f'Downloaded image for {card_name}')
        else:
            print(f'Failed to download image for {card_name}')
            print(f'HTTP status code: {response.status_code}')
            print(f'Attempted URL: {image_url}')


def ensure_card_images(decks):
    for deck in decks:
        for card in deck['cards']:
            get_card_image(card)


def initialize_session():
    if 'blacklist' not in session:
        session['blacklist'] = []
    if 'whitelist' not in session:
        session['whitelist'] = []


def filter_duel_decks(duel_decks, blacklist, whitelist):
    blacklist_set = set(blacklist)
    whitelist_set = set(whitelist)
    filtered_duel_decks = []

    for duel_deck in duel_decks:
        all_cards = set(card for deck in duel_deck.get('decks', []) for card in deck.get('cards', []))
        if all_cards & blacklist_set:
            continue
        if not whitelist_set.issubset(all_cards):
            continue
        filtered_duel_decks.append(duel_deck)

    return filtered_duel_decks


def get_common_cards(valid_duel_decks):
    common_cards = {
        card
        for duel_deck in valid_duel_decks
        for deck in duel_deck.get('decks', [])
        for card in deck.get('cards', [])
    }
    return sorted(common_cards)


@app.route('/', methods=['GET', 'POST'])
def index():
    initialize_session()
    allowed_repeated_cards_param = request.args.get('allowed_repeated_cards', '0')
    try:
        allowed_repeated_cards = int(allowed_repeated_cards_param)
    except ValueError:
        allowed_repeated_cards = 0

    blacklist = set(session.get('blacklist', []))
    whitelist = set(session.get('whitelist', []))
    valid_duel_decks = []
    decks = []
    filtered_valid_duel_decks = []

    if allowed_repeated_cards is not None:
        html_content = fetch_html(DECKS_URL)
        if html_content:
            decks = extract_decks(html_content)
            ensure_card_images(decks)
            valid_duel_decks = find_duel_decks(decks, allowed_repeated_cards)
            filtered_valid_duel_decks = filter_duel_decks(valid_duel_decks, blacklist, whitelist)

    common_cards = get_common_cards(valid_duel_decks)

    return render_template(
        'index.html',
        duel_decks=filtered_valid_duel_decks,
        allowed_repeated_cards=allowed_repeated_cards,
        common_cards=common_cards,
        blacklist=list(blacklist),
        whitelist=list(whitelist)
    )


@app.route('/add_to_blacklist', methods=['POST'])
def add_to_blacklist():
    card = request.form.get('card')
    if card:
        initialize_session()
        blacklist = set(session['blacklist'])
        blacklist.add(card)
        session['blacklist'] = list(blacklist)
    return redirect(url_for('index', allowed_repeated_cards=request.args.get('allowed_repeated_cards')))


@app.route('/remove_from_blacklist', methods=['POST'])
def remove_from_blacklist():
    card = request.form.get('card')
    if card:
        initialize_session()
        blacklist = set(session['blacklist'])
        blacklist.discard(card)
        session['blacklist'] = list(blacklist)
    return redirect(url_for('index', allowed_repeated_cards=request.args.get('allowed_repeated_cards')))


@app.route('/add_to_whitelist', methods=['POST'])
def add_to_whitelist():
    card = request.form.get('card')
    if card:
        initialize_session()
        whitelist = set(session['whitelist'])
        whitelist.add(card)
        session['whitelist'] = list(whitelist)
    return redirect(url_for('index', allowed_repeated_cards=request.args.get('allowed_repeated_cards')))


@app.route('/remove_from_whitelist', methods=['POST'])
def remove_from_whitelist():
    card = request.form.get('card')
    if card:
        initialize_session()
        whitelist = set(session['whitelist'])
        whitelist.discard(card)
        session['whitelist'] = list(whitelist)
    return redirect(url_for('index', allowed_repeated_cards=request.args.get('allowed_repeated_cards')))


@app.route('/clear_blacklist', methods=['POST'])
def clear_blacklist():
    initialize_session()
    session['blacklist'] = []
    return redirect(url_for('index', allowed_repeated_cards=request.args.get('allowed_repeated_cards')))


@app.route('/clear_whitelist', methods=['POST'])
def clear_whitelist():
    initialize_session()
    session['whitelist'] = []
    return redirect(url_for('index', allowed_repeated_cards=request.args.get('allowed_repeated_cards')))


if __name__ == '__main__':
    app.run(debug=True)