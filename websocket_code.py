import websocket
import json
import os
import uuid
import threading
import time
from datetime import datetime
import socket

ws_url = "wss://f11.reallivedealercasino.com/wssX40"
myId = None
action_count = 3
bet_count = 0
game_session_symbol = None
#auth_key = "9oKW25ctLlUhhREwhpQKqfHVkfSqX5"

card_values = {
    '2': 1, '3': 1, '4': 2, '5': 2, '6': 2,
    '7': 1, '8': 0, '9': -1,
    '10': -2, 'J': -2, 'Q': -2, 'K': -2, 'A': 0
}
stop_event = threading.Event()
min_balance_for_bet = {
    5: 40,
    12: 96,
    20: 160,
    30: 240,
    60: 480
}

shoe_end_timer = None
timer_started = False
TIMER_THRESHOLD = 30

occupied_seats = []


bet_placed = False

processed_game_ids = set()
true_count = 0
running_count = 0
decks_in_shoe = 6

current_placebet_amount = 0

current_bet_amount_from_server = 0
current_balance_from_server = 0

current_wagerresponse_amount = 0
is_restarting = False
game_id = None
current_balance = 0

discarded_cards_count = 0

waiting_for_seat_update = False  # Track if we're waiting for a SeatUpdate
joined_seats = 0  # Track number of seats joined after a BJCMessage

current_seat = None

offers_received_for_seat = {}
seats_to_surrender = []

offer_ids_by_seat = {}

cards_counted_mid_hand = {}

has_it_ran = False

def get_bet_amount(true_count):
   
    if 0.25 <= true_count <= 0.74:
        return 10
    elif 0.75 <= true_count <= 1.24:
        return 15
    elif 1.25 <= true_count <= 1.74:
        return 20
    elif 1.75 <= true_count <= 2.24:
        return 20
    elif 2.25 <= true_count <= 2.74:
        return 20
    elif 2.75 <= true_count <= 3.24:
        return 30
    elif 3.25 <= true_count <= 3.74:
        return 30
    elif 3.75 <= true_count <= 4.24:
        return 30
    elif 4.25 <= true_count <= 4.74:
        return 60
    elif 4.75 <= true_count <= 5.24:
        return 60
    elif 5.25 <= true_count <= 5.74:
        return 60
    elif 5.75 <= true_count <= 6.24:
        return 60
    elif 6.25 <= true_count <= 6.74:
        return 60
    elif 6.75 <= true_count <= 7.24:
        return 60
    elif 7.25 <= true_count:
        return 60
    else:
        return None


surrendered_seats = set()
hand_count =-1

def load_auth_key(file_path):
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("[ERROR] Authentication key file not found!")
        return None
    

auth_key = load_auth_key(os.path.join("/home", "tester", "Downloads", "externalAuthToken.txt"))
    
def save_counts_to_file(true_count, running_count,discarded_cards_count, file_path):
    with open(file_path, 'w') as f:
        f.write(f"{true_count}\n{running_count}\n{discarded_cards_count}")



def load_counts_from_file(file_path):
    try:
        with open(file_path, 'r') as f:
            true_count = float(f.readline().strip())
            running_count = int(f.readline().strip())
            discarded_cards_count = int(f.readline().strip())
            return true_count, running_count, discarded_cards_count
    except:
        return None, None, None

    

def manage_reconnection(ws):
    while True:
        time.sleep(300)  # Sleep for 30 seconds
        
        # Save counts before closing the connection
        save_counts_to_file(true_count, running_count, discarded_cards_count, os.path.join("/home", "tester", "Downloads", "counts_stored.txt"))
        
        global auth_key
        auth_key = load_auth_key(os.path.join("/home", "tester", "Downloads", "externalAuthToken.txt"))
        
        # Close the current connection; it'll be restarted by the main loop
        ws.close()
        #ws = None
        time.sleep(1)  # Wait a short while
        
        

def create_new_websocket():
    ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_open=on_open, on_close=on_close, on_error=on_error)
    return ws
        


def get_adjusted_bet_amount(bet_amount, balance):
    min_balance = min_balance_for_bet.get(bet_amount, 0)
    if balance < min_balance:
        adjusted_bet = (balance // 8)  # Find the maximum amount that can be bet using multiples of 12
        return adjusted_bet
    return bet_amount



def decompose_into_chips(amount):
    chip_values = [100, 25, 10, 5, 1]
    chips = []

    for chip in chip_values:
        while amount >= chip:
            chips.append(chip)
            amount -= chip

    return chips

def place_bet(ws, action, bet_type, amount, mode):
    global action_count
    global myId
    global game_session_symbol
    global game_id
    global bet_count
    global current_bet_amount_from_server
    global current_placebet_amount

    if game_session_symbol is None:
        print("[ERROR] Game session symbol is not set!")
        return

    chips = decompose_into_chips(amount) if mode != "undo" else [0]
    
    for chip in chips:
        bet_message = {
            "header": f"18,{myId},{action_count},0,7",
            "WagerRequest": {
                "currency": "USD",
                "action": action,
                "gameSessionId": game_session_symbol,
                "gameId": game_id,
                "betIds": [0] if mode == "undo" else [bet_count],
                "betTypes": [0] if mode == "undo" else [bet_type],
                "amounts": [0] if mode == "undo" else [chip]
            }
        }

        if mode == "test":
            print("[DEBUG] Would have sent WagerRequest:", json.dumps(bet_message))
        elif mode == "undo":
            print(f"[DEBUG] About to send undo bet request.")
            ws.send(json.dumps(bet_message))
            print("[DEBUG] Undo bet request sent successfully.")
        else:
            print(f"[DEBUG] About to send WagerRequest with bet_count {bet_count} and action {action}.")
            time.sleep(0.5)
            try:
                ws.send(json.dumps(bet_message))
                current_placebet_amount = amount
                print("THIS IS THE CURRENT PLACE BET AMOUNT AFTER IT IS SET TO AMOUNT: ", current_placebet_amount)
            except Exception as e:
                print(f"Failed to send message: {e}")
            print(f"[DEBUG] WagerRequest sent successfully with bet_count {bet_count} and action {action}.")
            print(f"[INFO] Sent {('bet' if action == 0 else 'undo bet')} of {chip} for Game ID {bet_message['WagerRequest']['gameId']}.")
        action_count += 1  # Increment the action count
        bet_count += 1

        

       
        print(f"[INFO] Sent {('bet' if action == 0 else 'undo bet')} of {chip} for Game ID {bet_message['WagerRequest']['gameId']}.")



def place_and_undo_bet(ws):
    global current_placebet_amount
    # Place a $5 bet on the first seat (betType=11)

    original_placebet_amount = current_placebet_amount

    place_bet(ws, 0, 11, 5, mode="real")
    
    # Wait for some time before undoing the bet (you can adjust this delay)
    time.sleep(1)
    
    # Undo the $5 bet on the first seat (betType=11)
    place_bet(ws, 2, 11, 5, mode="real")

    current_placebet_amount = original_placebet_amount


def identify_and_take_free_seat(response):
    global current_seat, action_count, joined_seats
    global true_count, occupied_seats, hand_count
    
    hand_count+=1

    if true_count <= 0 and (hand_count %3 !=0):  # Only attempt to take seats if true_count > 0
        print("[INFO] Not taking any seats as true count is not favorable and its not the third hand.")
        return
    
    seats = response.get("SeatUpdate", {}).get("seats", [])
    occupied_by_others = [seat_info["seat"] for seat_info in seats]
    available_seats = [seat_num for seat_num in range(1, 8) if seat_num not in occupied_by_others]
    
    occupied_seats.clear()
    
    
    
    
	
    for seat_num in available_seats[:2]:  # Only take up to 2 available seats
        occupied_seats.append(seat_num)
        take_seat_request = {
            "header": f"104,{myId},{action_count},0,7",
            "TakeSeatRequest": {
                "gameSessionId": game_session_symbol,
                "seatId": seat_num,
                "tableId": "X40"
            }
        }
        ws.send(json.dumps(take_seat_request))
        print(f"[INFO] Sent TakeSeatRequest for seat {seat_num}.")
        
        action_count += 1
        joined_seats += 1
        #time.sleep(0.5)
        
        if joined_seats >= 2:
            break
     

def handle_shoe_end():
    global true_count, running_count, bet_placed, timer_started
    print("[INFO] Shoe has ended.")
    
    # Reset counts
    true_count = 0
    running_count = 0
    discarded_cards_count =0
    adjust_count(0,1)
    
    file_path = os.path.join("/home", "tester", "Downloads", "game_recordsX.txt")
    with open(file_path, 'a') as f:
        f.write("===== END OF SHOE =====\n\n")
    
    if bet_placed:  # Check the flag here
        # Code to undo the bet
        print("[INFO] Undoing bet.")
        #place_bet(ws, 1, 0, 0, mode="undo")
        bet_placed = False  # Reset the flag

    timer_started = False  # Reset the flag



def adjust_count(card_rank, access=0):
    global running_count
    global discarded_cards_count
    global true_count 
    if card_rank not in card_values:
        print(f"[DEBUG] Unexpected card rank: {card_rank}")
    running_count += card_values.get(card_rank, 0)
    print(f"[DEBUG] Adjusted for card {card_rank}. Running count: {running_count}")

    discarded_cards_count += 1

    decks_remaining = (312 - discarded_cards_count) / 52.0

    #true_count = running_count / decks_remaining if decks_remaining != 0 else 0
    true_count = -1
    print(f"[DEBUG] True Count: {true_count}")
    print(f"[DEBUG] Running count: {running_count}")
    print(f"[DEBUG] Discarded cards count: {discarded_cards_count}")

    if(access==1):
        true_count = 0
        running_count = 0
        discarded_cards_count = 0
        file_path = os.path.join("/home", "tester", "Downloads", "true_counts.txt")
        with open(file_path, 'a') as f:
            f.write(f"True Count at end of shoe: {true_count}\n")
            f.write(f"Running Count at end of shoe: {running_count}\n")







def handle_no_more_bets(response):
    global occupied_seats, true_count, seats_to_surrender, offers_received_for_seat, cards_counted_mid_hand

    

    for hand in response["BJCMessage"]["playerHands"]:
        seat = hand["seat"]

        # If the seat is not in the list of occupied seats, skip processing it
        #if seat not in occupied_seats:
           # continue



        for card in hand['cards']:
            card_rank = card.split(":")[0][:-1]
            adjust_count(card_rank)
            cards_counted_mid_hand[card] = cards_counted_mid_hand.get(card, 0) + 1  # increment the card count

        dealer_up_card = response["BJCMessage"]["dealerHand"]['cards'][1].split(":")[0][:-1]
        
        # Check if the score is soft (contains a '/')
        if "/" in str(hand["score"]):
            print(f"[DEBUG] Skipping surrender check for seat {seat} due to soft score: {hand['score']}")
            continue  # Skip the rest of the loop for this hand
        
        player_score = int(hand["score"])

        if seat not in occupied_seats:
            continue
        
        #check pairs
        previous_card = None
        for card in hand['cards']:
            (card.split(":")[0][:-1])
            if previous_card and previous_card == card_rank:
                if(player_score == 16 and dealer_up_card in ['10', 'J', 'Q', 'K'] and true_count >=3):
                    if offers_received_for_seat.get(seat):
                        offer_id = offer_ids_by_seat.get(seat)
                        if offer_id:  
                            send_surrender_offer_request(seat, offer_id)
                    else:
                        seats_to_surrender.append(seat)
                elif(player_score == 14 and dealer_up_card in ['8'] and true_count >=22):
                    if offers_received_for_seat.get(seat):
                        offer_id = offer_ids_by_seat.get(seat)
                        if offer_id:  
                            send_surrender_offer_request(seat, offer_id)
                    else:
                        seats_to_surrender.append(seat)
                elif(player_score == 14 and dealer_up_card in ['9'] and true_count >= 12):
                    if offers_received_for_seat.get(seat):
                        offer_id = offer_ids_by_seat.get(seat)
                        if offer_id:  
                            send_surrender_offer_request(seat, offer_id)
                    else:
                        seats_to_surrender.append(seat)
                elif(player_score == 14 and dealer_up_card in ['10', 'J', 'Q', 'K'] and true_count >=2):
                    if offers_received_for_seat.get(seat):
                        offer_id = offer_ids_by_seat.get(seat)
                        if offer_id:  
                            send_surrender_offer_request(seat, offer_id)
                    else:
                        seats_to_surrender.append(seat)
                elif(player_score == 14 and dealer_up_card in ['A'] and true_count >= 10):
                    if offers_received_for_seat.get(seat):
                        offer_id = offer_ids_by_seat.get(seat)
                        if offer_id:  
                            send_surrender_offer_request(seat, offer_id)
                    else:
                        seats_to_surrender.append(seat)
            previous_card = card_rank
                
                    


        if (player_score == 15 and dealer_up_card in ['10', 'J', 'Q', 'K'] and true_count >= 0):
            if offers_received_for_seat.get(seat):
                offer_id = offer_ids_by_seat.get(seat)
                if offer_id:  
                    send_surrender_offer_request(seat, offer_id)
            else:
                seats_to_surrender.append(seat)

        elif (player_score == 16 and dealer_up_card in ['10', 'J', 'Q', 'K'] and true_count >= -4):
            if offers_received_for_seat.get(seat):
                offer_id = offer_ids_by_seat.get(seat)
                if offer_id:  
                    send_surrender_offer_request(seat, offer_id)
            else:
                seats_to_surrender.append(seat)
        elif (player_score == 17 and dealer_up_card in ['10', 'J', 'Q', 'K'] and true_count >= 23):
            if offers_received_for_seat.get(seat):
                offer_id = offer_ids_by_seat.get(seat)
                if offer_id:  
                    send_surrender_offer_request(seat, offer_id)
            else:
                seats_to_surrender.append(seat)

        elif (player_score == 14 and dealer_up_card in ['10', 'J', 'Q', 'K'] and true_count >= 6):
            if offers_received_for_seat.get(seat):
                offer_id = offer_ids_by_seat.get(seat)
                if offer_id:  
                    send_surrender_offer_request(seat, offer_id)
            else:
                seats_to_surrender.append(seat)
        elif (player_score == 13 and dealer_up_card in ['10', 'J', 'Q', 'K'] and true_count >= 13):
            if offers_received_for_seat.get(seat):
                offer_id = offer_ids_by_seat.get(seat)
                if offer_id:  
                    send_surrender_offer_request(seat, offer_id)
            else:
                seats_to_surrender.append(seat)

        
                seats_to_surrender.append(seat)
        elif (player_score == 14 and dealer_up_card in ['A'] and true_count >= 10):
            if offers_received_for_seat.get(seat):
                offer_id = offer_ids_by_seat.get(seat)
                if offer_id:  
                    send_surrender_offer_request(seat, offer_id)
            else:
                seats_to_surrender.append(seat)


def send_surrender_offer_request(seat, offer_id):
    global action_count
    seat_to_bettype_mapping = {
        1: 32,
        2: 34,
        3: 36,
        4: 38,
        5: 40,
        6: 42,
        7: 44
    }
    
    bet_type = seat_to_bettype_mapping.get(seat)

    take_offer_request = {
        "header": f"109,{myId},{action_count},0,7",
        "TakeOfferRequest": {
            "gameSessionId": game_session_symbol,
            "offerId": offer_id,
            "betType": bet_type,
            "option": "Surrender",
            "isChooseAhead": False
        }
    }

    try:
        ws.send(json.dumps(take_offer_request))
        print(f"[DEBUG] Sent surrender offer request for seat {seat}.")
        surrendered_seats.add(seat)
    except Exception as e:
        print(f"[ERROR] Failed to send surrender offer request: {e}")

    action_count += 1  # Increment the action count







def save_true_count():
    global running_count
    true_count = running_count / decks_in_shoe
    file_path = os.path.join("/home", "tester", "Downloads", "true_counts.txt")
    with open(file_path, 'a') as f:
        f.write(f"True Count at end of shoe: {true_count}\n")
        f.write(f"Running Count at end of shoe: {running_count}\n")

# Generate a new UUID
new_uuid = str(uuid.uuid4())




def on_message(ws, message):

    global myId, action_count, game_session_symbol, current_seat, waiting_for_seat_update, joined_seats, game_id, processed_game_ids
    global timer_started, shoe_end_timer, bet_placed, current_balance, true_count, current_placebet_amount, current_bet_amount_from_server
    global current_balance_from_server, running_count, offer_ids_by_seat, occupied_seats, offers_received_for_seat, seats_to_surrender
    global has_it_ran

    print("[INFO] Message received: ", message)
    response = json.loads(message)

    # ConnectResponse - Connect to the server
    if "ConnectResponse" in response:
        myId = response["ConnectResponse"]["myId"]
        auth_request = {
            "header": f"13,{myId},1,0,7",
            "AuthRequest": {
                "externalAuthToken": auth_key
            }
        }
        ws.send(json.dumps(auth_request))
        print("[INFO] Sent AuthRequest.")

    # AuthResponse - Authenticate using the provided auth key
    if "AuthResponse" in response:
        if myId is None:
            print("[ERROR] 'myId' not received yet.")
            return

        enter_table_request = {
            "header": f"16,{myId},2,0,7",
            "EnterTableRequest": {
                "tableId": "X40",
                "limitLevelId": "BOVL",
                "accountSessionId": auth_key  # Update this too
            }
        }
        ws.send(json.dumps(enter_table_request))
        print("[INFO] Sent EnterTableRequest.")

    # EnterTableResponse - Upon successful table join
    if "EnterTableResponse" in response:
        game_session_symbol = response["EnterTableResponse"]["gameSessionSymbol"]
        print("[INFO] Game session symbol has been set.")





    # New message handlers
    if "BJCMessage" in response and response["BJCMessage"]["state"] == "Place Your Bets":
        global game_id
        game_id = response['BJCMessage']['gameId']
        print(f"[INFO] Updated game ID for the next round to: {game_id}")
        
        waiting_for_seat_update = True
        joined_seats = 0

    if "SeatUpdate" in response and waiting_for_seat_update:
        waiting_for_seat_update = False  # Reset the flag
        identify_and_take_free_seat(response)  # Identify and join up to three seats

    if "TakeSeatResponse" in response:
        if response["TakeSeatResponse"]["status"] != 0:
            print(f"[ERROR] Failed to take seat {current_seat}. Reason: {response['TakeSeatResponse']['errorMsg']}")
            current_seat = None
        else:
            print(f"[INFO] Successfully took seat {current_seat}.")

    if "BJCMessage" in response and response["BJCMessage"]["state"] == "Done":
        offer_ids_by_seat.clear()
        



        game_id = response['BJCMessage']['gameId']

        # Check if this game ID has already been processed
        if game_id in processed_game_ids:
            print(f"[DEBUG] Game ID {game_id} has already been processed. Skipping.")
            return
        
        processed_game_ids.add(game_id)

        # Adjust count for player hands
        for hand in response["BJCMessage"]["playerHands"]:
            for card in hand['cards']:
                if card not in cards_counted_mid_hand or cards_counted_mid_hand[card] <= 0:  # Ensure the card hasn't been counted already
                    card_rank = card.split(":")[0][:-1]
                    print(f"[DEBUG] Parsed card rank from {card}: {card_rank}")
                    adjust_count(card_rank)
                else:
                    cards_counted_mid_hand[card] -= 1  # decrement the count of the card


        # Adjust count for dealer hand
        for card in response["BJCMessage"]["dealerHand"]['cards']:
            card_rank = card.split(":")[0][:-1]
            print(f"[DEBUG] Parsed card rank from {card}: {card_rank}")
            adjust_count(card_rank)


    

        
        file_path = os.path.join("/home", "tester", "Downloads", "game_recordsX.txt")
        print(f"[DEBUG] Attempting to save to file: {file_path}")  # Debug statement

        current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open(file_path, "a") as file:
                file.write(f"Timestamp: {current_timestamp}\n")
                file.write(f"Game ID: {response['BJCMessage']['gameId']}\n")
                for hand in response["BJCMessage"]["playerHands"]:
                    seat = hand["seat"]
                    cards = ', '.join(hand["cards"])
                    marker = "*" if seat in occupied_seats else ""
                    surrender_marker = "[SURRENDER]" if seat in surrendered_seats else ""
                    file.write(f"Seat {seat}{marker}: {cards} {surrender_marker}\n")
                dealer_cards = ', '.join(response["BJCMessage"]["dealerHand"]["cards"])
                file.write(f"Dealer: {dealer_cards}\n")
                file.write(f"Running Count: {running_count}\n")
                file.write(f"True Count: {true_count}\n")
                file.write(f"Bet Placed wagerrequest: {'Yes' if current_placebet_amount > 0 else 'No'}\n")
                file.write(f"Bet Amount wagerrequest: {current_placebet_amount}\n")
                file.write(f"Bet Amount (server/wagerresponse): {current_bet_amount_from_server}\n") 
                file.write(f"Balance (server/wageresponse): {current_balance_from_server}\n")
                file.write("-----\n")
            print(f"[DEBUG] Successfully saved to file.")  # Debug statement
        except Exception as e:
            print(f"[ERROR] Could not write to file. Reason: {e}")


        current_placebet_amount = 0
        current_seat = None  # Reset seat to ensure we verify our status in the next seat update
        has_it_ran = False

    if "WagerResponse" in response:

        

        current_bet_amount_from_server = response['WagerResponse']['betAmounts'][0]  # Add this lines
        current_balance_from_server = response['WagerResponse']['balances']['USD']

        if response["WagerResponse"]["betStatuses"][0] == 0:
            print(f"[INFO] Bet {'placed' if response['WagerResponse']['action'] == 0 else 'undone'} successfully for amount: {current_bet_amount_from_server}.")

        else:
            if 'gameId' in response['WagerResponse']:  # Check if 'gameId' is present
                print(f"[ERROR] Issue with placing/undoing bet for Game ID {response['WagerResponse']['gameId']} with status {response['WagerResponse']['betStatuses'][0]}.")
            else:
                print(f"[ERROR] Issue with placing/undoing bet. 'gameId' not found. Status: {response['WagerResponse']['betStatuses'][0]}")


    if "BalanceUpdate" in response:
        current_balance = float(response['BalanceUpdate']['balances']['USD'])
        print(f"[INFO] Updated balance: {current_balance} USD.")

        #if current_balance < 40:

            #print("[ERROR] Balance is below $40 Exiting program.")
            #ws.close()  # Close the WebSocket connection
            #os._exit(0)  # Immediately stop the script



    #count cards mid hand
    if not has_it_ran:  # Only proceed if the block hasn't been run before
        if "BJCMessage" in response and response["BJCMessage"]["state"] == "No More Bets":
            dealer_cards = response["BJCMessage"]["dealerHand"]['cards']
            if "?" in dealer_cards[0] and "?" not in dealer_cards[1]:  
                handle_no_more_bets(response)
                has_it_ran = True  # Set the flag to True after running the block

    #open offer for surrender
    if "OpenOffer" in response:
        seat_offered = None
        # Assuming the 'betTypeId' is directly mapped to the seat number.
        if response["OpenOffer"]["betTypeId"] == 32:
            seat_offered = 1
        elif response["OpenOffer"]["betTypeId"] == 34:
            seat_offered = 2
        elif response["OpenOffer"]["betTypeId"] == 36:
            seat_offered = 3
        elif response["OpenOffer"]["betTypeId"] == 38:
            seat_offered = 4
        elif response["OpenOffer"]["betTypeId"] == 40:
            seat_offered = 5
        elif response["OpenOffer"]["betTypeId"] == 42:
            seat_offered = 6
        elif response["OpenOffer"]["betTypeId"] == 44:
            seat_offered = 7
            
        # If the seat is one of the ones you occupied, and Surrender is an option:
        if seat_offered in occupied_seats and "Surrender" in response["OpenOffer"]["options"]:
            offer_id = response["OpenOffer"]["offerId"]
            offer_ids_by_seat[seat_offered] = offer_id
            offers_received_for_seat[seat_offered] = True
            print(f"[DEBUG] Stored offerId {offer_id} for seat {seat_offered}.")
            
            # Check if we need to send surrender offer for this seat
            if seat_offered in seats_to_surrender:
                send_surrender_offer_request(seat_offered, offer_id)
                seats_to_surrender.remove(seat_offered)


    if "TakeOfferResponse" in response:
        if response["TakeOfferResponse"]["status"] == 0:
            print(f"[INFO] Surrender confirmed for seat {response['TakeOfferResponse']['seat']}.")
        else:
            print(f"[ERROR] Issue with surrendering for seat {response['TakeOfferResponse']['seat']}. Reason: {response['TakeOfferResponse']['errorMsg']}")


    if "TimerState" in response:
        if response["TimerState"]["duration"] == 9000 and response["TimerState"]["from"] == 13000 and response["TimerState"]["state"] == 1:
            print("[INFO] TimerState message received. Preparing to place bet...")
            
            # Place the bet after receiving the TimerState message
            #place_and_undo_bet(ws)


            
            
            bet_amount = get_bet_amount(true_count)
            adjusted_bet_amount = get_adjusted_bet_amount(bet_amount, current_balance)
            print("THIS IS THE CURRENT BALANCE RIGHT NOW: ", current_balance)
            print("THIS IS THE ADJUSTED BET AMOUNT BEFORE BET IS PLACED: ", adjusted_bet_amount)
            print("THIS IS THE TRUE COUNT BEFORE BET IS PLACED: ", true_count)


            if adjusted_bet_amount is not None and adjusted_bet_amount > 0:


                seat_to_bettype_mapping = {
                1: 32,
                2: 34,
                3: 36,
                4: 38,
                5: 40,
                6: 42,
                7: 44
                }


                for seat in occupied_seats: 
                    bet_type = seat_to_bettype_mapping.get(seat)
                    if bet_type:
                        # Delay between each bet for server synchronization
                        time.sleep(1)
                        place_bet(ws, 0, bet_type, adjusted_bet_amount, mode="real")
                        time.sleep(1)
                        place_bet(ws, 1, 0,0, mode="undo")
                        
                
                bet_placed = True
            else:
                print("[INFO] Skipping bet due to low balance or invalid bet amount.")



    if "TimerState" in response:
        if response["TimerState"]["state"] == 6:
            if not timer_started:
                # Start a timer for 30 seconds to handle shoe end
                shoe_end_timer = threading.Timer(TIMER_THRESHOLD, handle_shoe_end)
                shoe_end_timer.start()
                timer_started = True
            
    if "BJCMessage" in response:
        if timer_started:
            # A BJCMessage has been received within the timer's duration
            # so we should cancel the timer
            shoe_end_timer.cancel()
            timer_started = False
        
        
    

def on_error(ws, error):
    print(f"[ERROR] {error}")

def on_open(ws):
    global true_count, running_count, discarded_cards_count

    # Load counts
    tc, rc, dcc = load_counts_from_file(os.path.join("/home", "tester", "Downloads", "counts_stored.txt"))
    if tc is not None and rc is not None and dcc is not None:
        true_count = tc
        running_count = rc
        discarded_cards_count = dcc



    new_uuid = str(uuid.uuid4())
    print("[INFO] WebSocket connection opened.")
    connect_request = {
        "header": "20,-1,0,0,7",
        "ConnectRequest": {
            "myId": -1,
            "version": {"major": 1, "minor": 1, "revision": 1},
            "uuid": new_uuid,
            "isDealerMonitor": False
        }
    }
    ws.send(json.dumps(connect_request))

def on_close(ws, close_status_code, close_message):
    print("[INFO] WebSocket connection closed. Code:", close_status_code, ". Message:", close_message)




ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_open=on_open, on_close=on_close, on_error=on_error)

# Start the manage_reconnection function in a separate thread
reconnection_thread = threading.Thread(target=manage_reconnection, args=(ws,))
reconnection_thread.daemon = True
reconnection_thread.start()

while True:  # Main loop to keep the WebSocket running
    try:
        ws.run_forever()
    except websocket._exceptions.WebSocketException as e:
        print(f"WebSocket Error: {e}")

        save_counts_to_file(true_count, running_count, discarded_cards_count, os.path.join("/home", "tester", "Downloads", "counts_stored.txt"))
        time.sleep(1)
        ws = create_new_websocket()