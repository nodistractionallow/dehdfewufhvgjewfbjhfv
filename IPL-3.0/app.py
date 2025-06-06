from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import mainconnect # Import the game logic from mainconnect.py
# from match_simulator import MatchSimulator # MatchSimulator is no longer actively used for new game initiation from UI
import os
import copy # For deepcopy if needed by process_batting_innings
import uuid # For unique match IDs
import logging # For logging errors
import re # For log parsing

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Temporary directory for storing match logs
TMP_LOG_DIR = os.path.join(app.root_path, 'tmp_match_logs')
if not os.path.exists(TMP_LOG_DIR):
    try:
        os.makedirs(TMP_LOG_DIR)
    except OSError as e:
        logging.error(f"Error creating temporary log directory {TMP_LOG_DIR}: {e}")


# --- Helper Functions ---
def load_teams():
    try:
        with open('teams/teams.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("teams/teams.json not found.")
        return {}
    except json.JSONDecodeError:
        logging.error("Could not decode JSON from teams/teams.json.")
        return {}

def process_batting_innings(bat_tracker_original):
    bat_tracker = copy.deepcopy(bat_tracker_original)
    wickets = 0
    for player, stats in bat_tracker.items():
        stats['how_out'] = "Not out"
        if not stats.get('ballLog'):
            stats['how_out'] = "DNB"
            stats['runs'] = stats.get('runs', '')
            stats['balls'] = stats.get('balls', '')
            continue
        wicket_found = False
        for log_entry in stats['ballLog']:
            parts = log_entry.split(':')
            if len(parts) > 1:
                event_details = parts[1]
                if event_details.startswith("W"):
                    wickets += 1
                    wicket_found = True
                    if "-CaughtBy-" in event_details:
                        try:
                            details = event_details.split('-')
                            catcher = details[details.index('CaughtBy') + 1]
                            bowler = details[details.index('Bowler') + 1]
                            stats['how_out'] = f"c {catcher} b {bowler}"
                        except (ValueError, IndexError): stats['how_out'] = "Caught"
                    elif "-runout" in event_details: stats['how_out'] = "Run out"
                    elif "-Bowler-" in event_details:
                        try:
                            details = event_details.split('-')
                            dismissal_type = details[0][1:]
                            bowler = details[details.index('Bowler') + 1]
                            stats['how_out'] = f"{dismissal_type} b {bowler}"
                        except (ValueError, IndexError): stats['how_out'] = "Wicket"
                    else: stats['how_out'] = "Wicket"
                    break
        if not wicket_found and stats.get('balls', 0) == 0 and stats.get('runs', 0) == 0:
            any_other_batted = False
            for p_stats_check in bat_tracker.values():
                if p_stats_check.get('balls',0) > 0 :
                    any_other_batted = True
                    break
            if any_other_batted :
                stats['how_out'] = "DNB"
    return bat_tracker, wickets

# Simplifies a detailed match event log into a list of outcomes (runs or "wicket")
# suitable for the Pygame animation.
def simplify_event_log(raw_log_entries):
    simplified_log = []
    # Regex patterns to identify key events in log strings.
    # Order of checks matters (e.g., FOUR/SIX before single digit runs).
    for entry in raw_log_entries:
        event_text = entry.get("event", "") # Get the raw event string

        # Check for explicit " FOUR" or " SIX"
        if " FOUR" in event_text:
            simplified_log.append(4)
            continue
        if " SIX" in event_text:
            simplified_log.append(6)
            continue

        # Attempt to find (W)icket or single (d)igit runs, typically formatted like " X Score:" or "W Score:"
        # This pattern looks for a space, then W or a digit, then a space, then expects "Score:" later in the string.
        match = re.search(r' (W|\d) (?=.*Score:)', event_text)
        if not match:
            # Fallback: look for W or 0-6 directly before " Score:" (no space after W/digit)
            match = re.search(r'(W|[0-6]) Score:', event_text)
        if not match:
            # Fallback for more verbose WICKET entries, e.g., "... WICKET Score: ..."
             match = re.search(r'\s(WICKET)\s+Score:', event_text, re.IGNORECASE)
             if match: outcome = "wicket"
             else: outcome = None
        else:
            outcome = match.group(1) # The captured group (W or digit)

        if outcome:
            if outcome == 'W' or outcome.upper() == 'WICKET':
                simplified_log.append("wicket")
            elif outcome.isdigit():
                simplified_log.append(int(outcome))
        # Handle extras like Wide (WD), No Ball (NB), Leg Bye (LB)
        elif "Wide" in event_text or "WD" in event_text:
            simplified_log.append(0) # Represent wide as 0 runs for animation log
        elif "LB" in event_text or "NB" in event_text:
            # Check if No Ball log specifies runs scored off it (e.g., "1 NB" or "NB 1")
            nb_runs_match = re.search(r'(\d(?=\sNB))|(NB\s\d)', event_text)
            if nb_runs_match:
                run_part = nb_runs_match.group(1) or nb_runs_match.group(2) # Get the digit part
                if run_part and run_part.isdigit(): simplified_log.append(int(run_part))
                else: simplified_log.append(0) # Default to 0 if runs not clearly specified with NB
            else:
                simplified_log.append(0) # Default for LB or NB without specified runs
        # If no specific outcome identified, it's not added to the simplified log.
        # This helps filter out non-scoring or non-wicket events if necessary.

    return [item for item in simplified_log if item is not None] # Clean out any None entries

# --- End Helper Functions ---

scores_dir_path = os.path.join(os.getcwd(), "scores")
os.makedirs(scores_dir_path, exist_ok=True)
for f_remove in os.listdir(scores_dir_path):
    if os.path.isfile(os.path.join(scores_dir_path, f_remove)):
        try: os.remove(os.path.join(scores_dir_path, f_remove))
        except OSError as e: logging.warning(f"Error removing file {f_remove} from scores dir: {e}")


@app.route('/', methods=['GET'])
def index():
    teams_data = load_teams()
    session.pop('full_match_data', None)
    session.pop('sim_state', None)
    session.pop('replay_match_id', None)
    return render_template('index.html', teams=teams_data, scorecard_data=None)

@app.route('/generate_scorecard', methods=['POST'])
def generate_scorecard():
    teams_data = load_teams()
    team1_code = request.form.get('selectedTeam1')
    team2_code = request.form.get('selectedTeam2')
    simulation_type = request.form.get('simulation_type')

    if not team1_code or not team2_code: return redirect(url_for('index', error_message="Please select two teams."))
    if team1_code == team2_code: return redirect(url_for('index', error_message="Please select two different teams."))
    if not simulation_type: return redirect(url_for('index', error_message="Please select a simulation type."))

    if simulation_type == 'direct':
        match_results = mainconnect.game(manual=False, sentTeamOne=team1_code, sentTeamTwo=team2_code, switch="webapp")

        team1_s_name = teams_data.get(team1_code, {}).get('name', team1_code)
        team2_s_name = teams_data.get(team2_code, {}).get('name', team2_code)
        team1_full_name = teams_data.get(team1_code, {}).get('fullName', team1_s_name)
        team2_full_name = teams_data.get(team2_code, {}).get('fullName', team2_s_name)

        innings1_battracker_processed, wickets1_fallen = process_batting_innings(match_results.get("innings1Battracker", {}))
        innings2_battracker_processed, wickets2_fallen = process_batting_innings(match_results.get("innings2Battracker", {}))

        scorecard_data_for_template = {
            "team1": team1_code, "team2": team2_code,
            "team1_full_name": team1_full_name,
            "team2_full_name": team2_full_name,
            "match_teams_title": f"{team1_full_name} vs {team2_full_name}",
            "tossMsg": match_results.get("tossMsg"),
            "innings1BatTeam": match_results.get("innings1BatTeam"), "innings1Runs": match_results.get("innings1Runs"),
            "innings1Wickets": wickets1_fallen, "innings1Balls": match_results.get("innings1Balls", 0),
            "innings1Battracker": innings1_battracker_processed, "innings1Bowltracker": match_results.get("innings1Bowltracker"),
            "innings2BatTeam": match_results.get("innings2BatTeam"), "innings2Runs": match_results.get("innings2Runs"),
            "innings2Wickets": wickets2_fallen, "innings2Balls": match_results.get("innings2Balls", 0),
            "innings2Battracker": innings2_battracker_processed, "innings2Bowltracker": match_results.get("innings2Bowltracker"),
            "winMsg": match_results.get("winMsg"), "winner": match_results.get("winner"),
            "innings1Log": match_results.get("innings1Log"), "innings2Log": match_results.get("innings2Log")
        }
        return render_template('index.html', teams=teams_data, scorecard_data=scorecard_data_for_template)

    elif simulation_type == 'ball_by_ball':
        match_results = mainconnect.game(manual=False, sentTeamOne=team1_code, sentTeamTwo=team2_code, switch="webapp_full_log")
        innings1_battracker_original = match_results.get("innings1Battracker", {})
        innings2_battracker_original = match_results.get("innings2Battracker", {})
        processed_bat_tracker1, wickets1_fallen = process_batting_innings(innings1_battracker_original)
        processed_bat_tracker2, wickets2_fallen = process_batting_innings(innings2_battracker_original)
        team1_full_data = teams_data.get(team1_code, {})
        team2_full_data = teams_data.get(team2_code, {})

        full_match_data_to_save = {
            "toss_msg": match_results.get("tossMsg"), "team1_code": team1_code, "team2_code": team2_code,
            "team1_data": team1_full_data, "team2_data": team2_full_data,
            "innings1_log": match_results.get("innings1Log", []), "innings2_log": match_results.get("innings2Log", []),
            "innings1_bat_team": match_results.get("innings1BatTeam"), "innings2_bat_team": match_results.get("innings2BatTeam"),
            "innings1_runs": match_results.get("innings1Runs"), "innings1_wickets": wickets1_fallen,
            "innings1_balls": match_results.get("innings1Balls", 0),
            "innings2_runs": match_results.get("innings2Runs"), "innings2_wickets": wickets2_fallen,
            "innings2_balls": match_results.get("innings2Balls", 0),
            "win_msg": match_results.get("winMsg"), "winner": match_results.get("winner"),
            "innings1_battracker": processed_bat_tracker1, "innings2_battracker": processed_bat_tracker2,
            "innings1_bowltracker": match_results.get("innings1Bowltracker", {}),
            "innings2_bowltracker": match_results.get("innings2Bowltracker", {})
        }

        match_id = str(uuid.uuid4())
        tmp_file_path = os.path.join(TMP_LOG_DIR, f"match_log_{match_id}.json")

        try:
            with open(tmp_file_path, 'w') as f:
                json.dump(full_match_data_to_save, f)
            session['replay_match_id'] = match_id
        except IOError as e:
            logging.error(f"Error saving match log to {tmp_file_path}: {e}")
            return redirect(url_for('index', error_message="Failed to save match data for replay."))

        return redirect(url_for('replay_match_view'))
    else:
        return redirect(url_for('index', error_message="Invalid simulation type selected."))

@app.route('/replay_match_view')
def replay_match_view():
    match_id = session.get('replay_match_id')
    if not match_id:
        return redirect(url_for('index', error_message="No match ID found for replay."))

    tmp_file_path = os.path.join(TMP_LOG_DIR, f"match_log_{match_id}.json")

    try:
        with open(tmp_file_path, 'r') as f:
            full_match_data = json.load(f)
    except FileNotFoundError:
        logging.error(f"Match log file not found: {tmp_file_path}")
        session.pop('replay_match_id', None)
        return redirect(url_for('index', error_message="Match data not found. It might have expired or an error occurred."))
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding match log JSON from {tmp_file_path}: {e}")
        session.pop('replay_match_id', None)
        return redirect(url_for('index', error_message="Error reading match data."))

    team1_s_name = full_match_data.get('team1_data', {}).get('name', full_match_data.get('team1_code', 'Team 1'))
    team2_s_name = full_match_data.get('team2_data', {}).get('name', full_match_data.get('team2_code', 'Team 2'))

    return render_template('replay_ball_by_ball.html',
                           full_match_data=full_match_data,
                           team1_short_name=team1_s_name,
                           team2_short_name=team2_s_name)

# Route to render the animation player HTML page.
# This page will load Pyodide and the Pygame animation script.
@app.route('/play_animation')
def play_animation():
    # This route can be used if we want to navigate to the animation player
    # without pre-loading specific match data (e.g., allowing user to select log in Pygame UI).
    return render_template('animation_player.html') # match_data_json is not passed here

# Route to set up and launch the cricket animation with specific match data.
# It simulates a match, processes the log, and passes data to the animation player.
@app.route('/setup_animation', methods=['POST'])
def setup_animation():
    teams_data = load_teams() # Load team information (names, colors, etc.)
    team1_code = request.form.get('selectedTeam1') # Get selected Team 1 from form
    team2_code = request.form.get('selectedTeam2') # Get selected Team 2 from form

    # Basic validation for team selection
    if not team1_code or not team2_code:
        return redirect(url_for('index', error_message="Please select two teams for animation."))
    if team1_code == team2_code:
        return redirect(url_for('index', error_message="Please select two different teams."))

    # Simulate a full match to get the logs.
    # "webapp_full_log" switch ensures detailed logs are generated by mainconnect.py.
    match_results = mainconnect.game(manual=False, sentTeamOne=team1_code, sentTeamTwo=team2_code, switch="webapp_full_log")

    raw_log_to_process = []
    batting_team_animation = "" # Team that will be shown batting in animation (Team A)
    bowling_team_animation = "" # Team that will be shown bowling in animation (Team B)

    # Determine which innings log to use for the animation.
    # The animation is currently set up for one innings. We prioritize team1_code as the batting team.
    if match_results.get("innings1BatTeam", "").lower() == team1_code.lower():
        raw_log_to_process = match_results.get("innings1Log", [])
        batting_team_animation = team1_code
        bowling_team_animation = team2_code
    elif match_results.get("innings2BatTeam", "").lower() == team1_code.lower():
        raw_log_to_process = match_results.get("innings2Log", [])
        batting_team_animation = team1_code
        bowling_team_animation = team2_code
    else:
        # Fallback: if team1_code didn't bat for some reason, use the first innings log.
        raw_log_to_process = match_results.get("innings1Log", [])
        batting_team_animation = match_results.get("innings1BatTeam", team1_code)
        # Ensure bowling_team_animation is correctly set to the other team.
        if batting_team_animation.lower() == team1_code.lower():
            bowling_team_animation = team2_code
        else:
            bowling_team_animation = team1_code

    # Convert the raw textual event log into a simplified list of outcomes for Pygame.
    simplified_animation_log = simplify_event_log(raw_log_to_process)

    # If log simplification fails or results in an empty log, use a default test log.
    if not simplified_animation_log:
        simplified_animation_log = [0, 1, 4, "wicket", 6, 0, 0, 0, 2, 0, 1, 0, 4, 0, "wicket", 6, 0, 1, 2, 0] # Default for testing

    # Get team details (name, colors) from loaded team data.
    team_a_info = teams_data.get(batting_team_animation.lower(), {})
    team_b_info = teams_data.get(bowling_team_animation.lower(), {})

    # Helper to convert hex color strings (e.g., "#RRGGBB") to RGB tuples (R,G,B) for Pygame.
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (0,0,255) # Default to blue if hex string is invalid

    # Prepare data structure to be passed to the animation player template.
    match_data = {
        "team_a_name": team_a_info.get("name", batting_team_animation),
        "team_b_name": team_b_info.get("name", bowling_team_animation),
        "team_a_color_hex": team_a_info.get("colorPrimary", "#0000FF"), # Default blue
        "team_b_color_hex": team_b_info.get("colorPrimary", "#FF0000"), # Default red
        "log": simplified_animation_log
    }

    # Render the animation player, passing the match data as a JSON string.
    return render_template('animation_player.html', match_data_json=json.dumps(match_data))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
