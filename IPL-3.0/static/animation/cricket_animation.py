import asyncio
import platform
import pygame
import random
import math
if platform.system() == "Emscripten":
    import js # For accessing Pyodide global scope if running in Pyodide

# --- Constants ---
# Screen and FPS
PLAYER_RADIUS = 15; FIELDER_RADIUS = 12; BALL_RADIUS = 5; FPS = 60; SCREEN_WIDTH = 1280; SCREEN_HEIGHT = 720
# Colors
WHITE = (255,255,255); BLACK = (0,0,0); LIGHT_BROWN = (210,180,140); GREEN = (34,139,34)
RED = (255,0,0); BLUE = (0,0,255); YELLOW = (255,255,0); SKY_BLUE = (135,206,235)
GREY = (200,200,200); DARK_GREY = (100,100,100); CROWD_COLOR_PLACEHOLDER = (160,160,160)
STUMP_COLOR = (245, 245, 220); STUMP_HIT_COLOR = (255, 69, 0)
# Team colors (fallback if not provided by Flask)
TEAM_COLORS = {"India":BLUE,"Australia":YELLOW,"England":(200,0,0),"Pakistan":(0,128,0),"South Africa":(0,102,0),"New Zealand":BLACK}
# Log outcomes for internal UI
VALID_LOG_OUTCOMES = ["0","1","2","3","4","6","wicket"]
# Pitch and Crease Dimensions
PITCH_WIDTH = 60; PITCH_LENGTH = 400; PITCH_X = SCREEN_WIDTH//2-PITCH_WIDTH//2
PITCH_Y_BOWLER_END = SCREEN_HEIGHT*0.25; PITCH_Y_BATSMAN_END = PITCH_Y_BOWLER_END+PITCH_LENGTH
CREASE_LENGTH = PITCH_WIDTH+20; POPPING_CREASE_Y_BOWLER = int(PITCH_Y_BOWLER_END+PITCH_LENGTH*0.1)
POPPING_CREASE_Y_BATSMAN = int(PITCH_Y_BATSMAN_END-PITCH_LENGTH*0.1)
STUMPS_LINE_Y_BOWLER = int(PITCH_Y_BOWLER_END+PITCH_LENGTH*0.05)
STUMPS_LINE_Y_BATSMAN = int(PITCH_Y_BATSMAN_END-PITCH_LENGTH*0.05)
STUMP_HEIGHT = 25; STUMP_WIDTH = 3; STUMPS_GAP = 5

# Animation Timing & Parameters
BOWLER_START_RUNUP_OFFSET = 80; BOWLER_RUNUP_FRAMES = 12; BOWLER_ACTION_FRAMES = 5*2 # Bowler animation
BALL_TRAVEL_TOTAL_FRAMES = 25; BALL_GRAVITY = 0.3; BALL_BOUNCE_FACTOR = -0.6 # Ball physics
PITCH_BOUNCE_POINT_OFFSET = PITCH_LENGTH*0.25 # Where ball aims to bounce
BATSMAN_ACTION_TOTAL_FRAMES = 15 # Batsman animation
FIELDER_SPEED = 1.5; FIELDER_MAX_MOVE_FRAMES = FPS // 2 # Fielder movement
CROWD_AREA_HEIGHT = SCREEN_HEIGHT * 0.20 # Crowd display area
CROWD_FAN_COLORS = [(200,50,50), (50,50,200), (50,150,50), (180,180,30), (100,100,100), (220,120,30)] # Crowd colors

# Animation Phases (States for the animation state machine)
ANIMATION_PHASE_PRE_BALL="pre_ball";ANIMATION_PHASE_BOWLER_RUNUP="bowler_runup";ANIMATION_PHASE_BOWLER_ACTION="bowler_action"
ANIMATION_PHASE_BALL_TRAVEL="ball_travel";ANIMATION_PHASE_BATSMAN_ACTION="batsman_action";ANIMATION_PHASE_FIELDING="fielding"
ANIMATION_PHASE_SHOWING_OUTCOME="showing_outcome";ANIMATION_PHASE_PAUSED="paused";ANIMATION_PHASE_MATCH_OVER="match_over"

# Displays match scores and information.
class Scoreboard:
    def __init__(self, font, screen_width):
        self.font = font; self.screen_width = screen_width; self.team_a_name = "Team A"; self.team_b_name = "Team B"; self.batting_team_name = ""; self.score = 0; self.wickets = 0; self.overs_done = 0; self.balls_in_current_over = 0; self.max_overs = 3; self.last_ball_outcome_display = "-"; self.target = 0; self.text_color = BLACK; self.bg_color = (220, 220, 220, 200); self.padding = 10; self.line_height = font.get_linesize() + 4; self.y_position = 45
    # Sets team names and current batting team.
    def set_teams(self, ta, tb, btf): self.team_a_name=ta; self.team_b_name=tb; self.batting_team_name=btf; self.max_overs=(20//6)+(1 if (20%6)>0 else 0) # Max overs for 20-ball log
    # Updates scoreboard data based on ball outcome.
    def update(self, r, w, ts, tw, tbb):
        self.score=ts; self.wickets=tw;
        if tbb>=0: self.overs_done=tbb//6; self.balls_in_current_over=tbb%6
        else: self.overs_done=0; self.balls_in_current_over=0
        if w: self.last_ball_outcome_display="WICKET!"
        elif isinstance(r,int): self.last_ball_outcome_display=str(r)
        elif isinstance(r,str) and r=="wicket": self.last_ball_outcome_display="WICKET!"
        else: self.last_ball_outcome_display="-"
    # Renders the scoreboard on the given surface.
    def draw(self,s):
        score_txt=f"{self.batting_team_name}: {self.score} / {self.wickets}"; ov_txt=f"Overs: {self.overs_done}.{self.balls_in_current_over} / {self.max_overs}";lb_txt=f"Last Ball: {self.last_ball_outcome_display}";
        sc_s=self.font.render(score_txt,True,self.text_color);ov_s=self.font.render(ov_txt,True,self.text_color);lb_s=self.font.render(lb_txt,True,self.text_color);
        max_w=max(sc_s.get_width(),ov_s.get_width(),lb_s.get_width());tot_h=3*self.line_height+2*self.padding;bg_w=max_w+2*self.padding;
        bg_x=self.screen_width-bg_w-10;bg_y=self.y_position;
        sb_bg_s=pygame.Surface((bg_w,tot_h),pygame.SRCALPHA);sb_bg_s.fill(self.bg_color);s.blit(sb_bg_s,(bg_x,bg_y));
        s.blit(sc_s,(bg_x+self.padding,bg_y+self.padding));s.blit(ov_s,(bg_x+self.padding,bg_y+self.padding+self.line_height));s.blit(lb_s,(bg_x+self.padding,bg_y+self.padding+2*self.line_height))

# Represents a cricket team with a name and color.
class Team:
    def __init__(self, name, color_tuple): self.name = name; self.color = color_tuple # color_tuple is (R,G,B)
# Represents the bowler with animation states for run-up and action.
class Bowler:
    def __init__(self,c,x,y):self.color=c;self.initial_x=x;self.initial_y=y;self.x=x;self.y=y;self.radius=PLAYER_RADIUS;self.action_total_frames=BOWLER_ACTION_FRAMES;self.action_current_frame=0;self.runup_total_frames=BOWLER_RUNUP_FRAMES;self.runup_current_frame=0;self.start_runup_y=self.y-BOWLER_START_RUNUP_OFFSET;self.bowling_crease_y=self.y;self.arm_angle=0;self.is_releasing_ball=False
    # Resets bowler to start of run-up position and animation state.
    def reset_state(self,bcy):self.x=self.initial_x;self.bowling_crease_y=bcy;self.start_runup_y=self.bowling_crease_y-BOWLER_START_RUNUP_OFFSET;self.y=self.start_runup_y;self.runup_current_frame=0;self.action_current_frame=0;self.arm_angle=0;self.is_releasing_ball=False
    # Draws the bowler and their animated arm.
    def draw(self,s):pygame.draw.circle(s,self.color,(int(self.x),int(self.y)),self.radius);pygame.draw.circle(s,BLACK,(int(self.x),int(self.y)),self.radius,1);al=self.radius*1.5;ax=self.x+al*math.cos(math.radians(self.arm_angle));ay=self.y-al*math.sin(math.radians(self.arm_angle));pygame.draw.line(s,BLACK,(int(self.x),int(self.y)),(int(ax),int(ay)),4)
    # Updates bowler's position during run-up. Returns False when run-up is complete.
    def update_runup(self):
        if self.runup_current_frame<self.runup_total_frames:self.runup_current_frame+=1;p=self.runup_current_frame/self.runup_total_frames;self.y=self.start_runup_y+(self.bowling_crease_y-self.start_runup_y)*p;return True
        self.y=self.bowling_crease_y;return False
    # Updates bowler's arm animation during bowling action. Sets is_releasing_ball flag. Returns False when action is complete.
    def update_action(self):
        if self.action_current_frame<self.action_total_frames:self.action_current_frame+=1;pd=self.action_total_frames//5;cp=self.action_current_frame//pd # 5 conceptual poses
        if cp==0:self.arm_angle=45 # Arm back
        elif cp==1:self.arm_angle=90 # Arm high
        elif cp==2:self.arm_angle=135;self.is_releasing_ball=True # Release point
        elif cp==3:self.arm_angle=180;self.is_releasing_ball=False # Follow through
        elif cp>=4:self.arm_angle=225 # Action complete
        return True
        self.is_releasing_ball=False;return False # Should be outside if block if logic is frame-based
# Represents the batsman with animation states for shots.
class Batsman:
    def __init__(self,c,x,y):self.color=c;self.x=x;self.y=y;self.radius=PLAYER_RADIUS;self.bat_width_orig=8;self.bat_height_orig=40;self.bat_color=(139,69,19);self.bat_rect=pygame.Rect(0,0,0,0);self.bat_angle=0;self.bat_draw_x_offset=self.radius;self.action_frames_total=BATSMAN_ACTION_TOTAL_FRAMES;self.action_current_frame=0;self.current_action="idle"
    # Draws the batsman and their animated bat.
    def draw(self,s):
        pygame.draw.circle(s,self.color,(self.x,self.y),self.radius)
        pygame.draw.circle(s,BLACK,(self.x,self.y),self.radius,1)
        bp_x=self.x+self.bat_draw_x_offset
        bp_y=self.y
        pts=[(-self.bat_width_orig/2,-self.bat_height_orig/2),(self.bat_width_orig/2,-self.bat_height_orig/2),(self.bat_width_orig/2,self.bat_height_orig/2),(-self.bat_width_orig/2,self.bat_height_orig/2)]
        rp=[]
        for px,py in pts:rx=px*math.cos(math.radians(self.bat_angle))-py*math.sin(math.radians(self.bat_angle));ry=px*math.sin(math.radians(self.bat_angle))+py*math.cos(math.radians(self.bat_angle));rp.append((bp_x+rx,bp_y+ry))
        pygame.draw.polygon(s,self.bat_color,rp)
    # Initiates a batsman action based on the ball outcome.
    def start_action(self,outcome):
        self.action_current_frame=0
        if isinstance(outcome,int): # Runs scored
            if outcome==0:self.current_action="defensive"
            elif outcome in[1,2,3]:self.current_action="push"
            elif outcome==4:self.current_action="drive"
            elif outcome==6:self.current_action="six_swing"
        elif outcome=="wicket":self.current_action="wicket_bowled" # Bowled animation
        else:self.current_action="idle" # Default
        # Set initial bat angle for the action
        if self.current_action=="defensive" or self.current_action=="push":self.bat_angle=0
        elif self.current_action=="drive":self.bat_angle=-15
        elif self.current_action=="six_swing":self.bat_angle=-45
        elif self.current_action=="wicket_bowled":self.bat_angle=20
        else:self.bat_angle=0
    # Updates the bat animation. Returns False when animation is complete.
    def update_animation(self):
        if self.action_current_frame>=self.action_frames_total:self.current_action="idle";self.bat_angle=0;return False # Reset to idle
        self.action_current_frame+=1;p=self.action_current_frame/self.action_frames_total # Progress of animation (0 to 1)
        # Animate bat angle based on current action type
        if self.current_action=="defensive":self.bat_angle=0
        elif self.current_action=="push":self.bat_angle=10*math.sin(p*math.pi) # Simple forward push
        elif self.current_action=="drive":self.bat_angle=-30+60*math.sin(p*math.pi) # Swing forward
        elif self.current_action=="six_swing":self.bat_angle=-60+90*math.sin(p*math.pi) # Lofted swing
        # wicket_bowled pose is static, no change needed here based on progress
        return True

# Represents the cricket ball with trajectory and shadow.
class Ball:
    def __init__(self,x,y):
        self.initial_x=x;self.initial_y=y;self.x=x;self.y=y;self.radius=BALL_RADIUS;self.color=RED;self.visible=True
        self.start_x,self.start_y=0,0;self.target_x,self.target_y=0,0;self.pitch_bounce_y_coord=0;self.vel_x,self.vel_y=0,0
        self.gravity=BALL_GRAVITY;self.bounce_factor=BALL_BOUNCE_FACTOR;self.total_travel_frames=BALL_TRAVEL_TOTAL_FRAMES
        self.current_travel_frame=0;self.has_bounced=False
        # Shadow attributes
        self.shadow_color = (50, 50, 50, 100); self.shadow_max_size_factor = 1.5; self.shadow_min_size_factor = 0.8; self.shadow_max_dist_for_full_size = PITCH_LENGTH / 3
    # Draws the ball and its shadow.
    def draw(self, surface):
        if self.visible:
            # Shadow drawing logic
            shadow_plane_y = STUMPS_LINE_Y_BATSMAN - 5 # Y-coordinate on pitch where shadow is cast
            is_ball_within_pitch_height_for_shadow = self.y < shadow_plane_y + 20 # Only draw shadow if ball is somewhat above pitch
            if self.y < shadow_plane_y and is_ball_within_pitch_height_for_shadow: # Ball is above the shadow plane
                height_above_plane = shadow_plane_y - self.y
                # Scale shadow size and alpha based on ball's height
                size_scale_factor = max(0, 1 - height_above_plane / self.shadow_max_dist_for_full_size)
                shadow_radius_x = self.radius * (self.shadow_min_size_factor + (self.shadow_max_size_factor - self.shadow_min_size_factor) * size_scale_factor)
                shadow_radius_y = shadow_radius_x * 0.5; shadow_radius_x = max(1, shadow_radius_x); shadow_radius_y = max(1, shadow_radius_y) # Elliptical and min size
                alpha_scale_factor = max(0.1, min(1, 1 - height_above_plane / (self.shadow_max_dist_for_full_size * 1.5)))
                current_shadow_alpha = int(self.shadow_color[3] * alpha_scale_factor)
                final_shadow_color = (self.shadow_color[0], self.shadow_color[1], self.shadow_color[2], current_shadow_alpha)
                shadow_rect_dims = (2 * shadow_radius_x, 2 * shadow_radius_y); shadow_rect_pos = (self.x - shadow_radius_x, shadow_plane_y - shadow_radius_y)
                try:
                    shadow_surface = pygame.Surface(shadow_rect_dims, pygame.SRCALPHA) # Use SRCALPHA for transparency
                    pygame.draw.ellipse(shadow_surface, final_shadow_color, (0,0, shadow_rect_dims[0], shadow_rect_dims[1]))
                    surface.blit(shadow_surface, shadow_rect_pos)
                except pygame.error: pass # Ignore errors if shadow dimensions are too small
            # Draw the ball itself
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
    # Initializes ball's trajectory towards the batsman.
    def start_travel(self,sp,tp,pby):self.x,self.y=sp;self.start_x,self.start_y=sp;self.target_x,self.target_y=tp;self.pitch_bounce_y_coord=pby;self.current_travel_frame=0;self.has_bounced=False;self.visible=True;dx=self.target_x-self.start_x;ttba=self.total_travel_frames/2.2 if self.total_travel_frames > 0 else 1; self.vel_x=dx/self.total_travel_frames if self.total_travel_frames > 0 else 0; self.vel_y=(self.pitch_bounce_y_coord-self.start_y-0.5*self.gravity*(ttba**2))/ttba if ttba > 0 else -2; # Calculate initial y-velocity for parabolic arc
                                     if self.vel_y > 0 and self.start_y < self.pitch_bounce_y_coord : self.vel_y *=-0.5; # Adjust if starting low
                                     if self.vel_y == 0 and self.vel_x == 0 : self.vel_y = -2 # Ensure some movement
    # Updates ball's position based on velocity, gravity, and bounce. Returns False if travel is complete.
    def update_trajectory(self):
        if not self.visible or self.current_travel_frame>=self.total_travel_frames: self.visible=False; return False
        self.current_travel_frame+=1;self.x+=self.vel_x;self.y+=self.vel_y;self.vel_y+=self.gravity # Apply physics
        # Bounce logic
        if not self.has_bounced and self.y>=self.pitch_bounce_y_coord:self.y=self.pitch_bounce_y_coord;self.vel_y*=self.bounce_factor;self.has_bounced=True
        # Stop conditions
        if self.has_bounced and self.y>=self.target_y and self.vel_y > 0 : self.visible=False; return False # Passed batsman after bounce
        if self.y > SCREEN_HEIGHT + self.radius : self.visible=False; return False # Off screen low
        if self.vel_y < 0 and self.y < PITCH_Y_BOWLER_END - self.radius*10 : self.visible=False; return False # Gone too high (e.g. top edge)
        return True

# Represents a fielder with basic movement logic.
class Fielder:
    def __init__(self,c,x,y):self.color=c;self.x=x;self.y=y;self.radius=FIELDER_RADIUS;self.original_x,self.original_y=x,y;self.target_x,self.target_y=x,y;self.is_moving=False;self.speed=FIELDER_SPEED;self.action_frames=0;self.max_action_frames=FIELDER_MAX_MOVE_FRAMES
    # Draws the fielder.
    def draw(self,s):pygame.draw.circle(s,self.color,(int(self.x),int(self.y)),self.radius);pygame.draw.circle(s,BLACK,(int(self.x),int(self.y)),self.radius,1)
    # Starts fielder's movement towards a target.
    def start_move(self,tx,ty):self.target_x=tx;self.target_y=ty;self.is_moving=True;self.action_frames=0
    # Updates fielder's position during movement. Returns False when movement is complete.
    def update_movement(self):
        if not self.is_moving:return False
        self.action_frames+=1
        if self.action_frames>=self.max_action_frames:self.is_moving=False;self.reset_position();return False # Stop and reset if max frames reached
        dx=self.target_x-self.x;dy=self.target_y-self.y;dist=math.hypot(dx,dy) # Distance to target
        if dist<self.speed:self.x,self.y=self.target_x,self.target_y;self.is_moving=False;return False # Snap to target if close
        self.x+=(dx/dist)*self.speed;self.y+=(dy/dist)*self.speed;return True # Move towards target
    # Resets fielder to their original position.
    def reset_position(self):self.x,self.y=self.original_x,self.original_y;self.target_x,self.target_y=self.original_x,self.original_y;self.is_moving=False;self.action_frames=0
# Represents the crowd with reaction animations.
class Crowd:
    def __init__(self, area_rect, num_fans_approx=150):self.area_rect=area_rect;self.fans=[];self.current_reaction_level=0;self.reaction_duration_frames=FPS*2;self.reaction_timer=0;self.wave_time=0
        # Initialize individual fans with properties for animation
        for _ in range(num_fans_approx):fan_w=random.randint(6,12);fan_h=random.randint(12,20);fan_x=random.randint(self.area_rect.left,self.area_rect.right-fan_w);y_b=random.choices([0.5,0.6,0.7,0.8,0.9,1.0],weights=[2,3,4,5,4,2],k=1)[0];fan_y_o=self.area_rect.top+self.area_rect.height*y_b-fan_h;self.fans.append({'rect':pygame.Rect(fan_x,fan_y_o,fan_w,fan_h),'y_orig':fan_y_o,'y_offset':0,'color':random.choice(CROWD_FAN_COLORS),'anim_speed_factor':random.uniform(0.8,1.2),'anim_amplitude_base':random.uniform(1,3)})
    # Sets the crowd's reaction level based on the ball outcome.
    def set_reaction(self,outcome):new_reaction_level=0
        if isinstance(outcome,str)and outcome=="wicket":new_reaction_level=2 # High excitement for wicket
        elif isinstance(outcome,int): # Numerical outcomes (runs)
            if outcome==6 or outcome==4:new_reaction_level=2 # High excitement for boundaries
            elif outcome>=1:new_reaction_level=1 # Mild excitement for other scores
            else:new_reaction_level=0 # Idle for 0 runs
        if new_reaction_level>self.current_reaction_level:self.current_reaction_level=new_reaction_level;self.reaction_timer=self.reaction_duration_frames # Escalate excitement
        elif new_reaction_level==0 and self.current_reaction_level!=0:self.reaction_timer=FPS//3 # Briefly show no reaction then idle
        elif self.current_reaction_level==0 and new_reaction_level==0:self.reaction_timer=0 # Stay idle
    # Updates fan animations based on current reaction level.
    def update(self):self.wave_time+=0.15 # General timer for sine wave
        if self.reaction_timer>0:self.reaction_timer-=1
        if self.reaction_timer==0:self.current_reaction_level=0 # Return to idle after timer
        for fan in self.fans:amplitude=0;eff_speed=fan['anim_speed_factor']
        if self.current_reaction_level==1:amplitude=fan['anim_amplitude_base']*1.5;eff_speed*=1.2 # Mild wave
        elif self.current_reaction_level==2:amplitude=fan['anim_amplitude_base']*2.5;eff_speed*=1.5 # Excited wave
        if amplitude>0:fan['y_offset']=math.sin(self.wave_time*eff_speed+fan['rect'].x*0.05)*amplitude # Sin wave for y-offset
        else:fan['y_offset']=0 # Idle
    # Draws the crowd fans.
    def draw(self,s):
        for fan in self.fans:final_y=fan['y_orig']+fan['y_offset'];pygame.draw.ellipse(s,fan['color'],pygame.Rect(fan['rect'].left,final_y,fan['rect'].width,fan['rect'].height))

# Main game class, manages game state, elements, and animation flow.
class CricketGame:
    def __init__(self):
        pygame.init(); pygame.font.init() # Initialize Pygame and font module
        # Setup screen and fonts
        self.font = pygame.font.Font(None, 30); self.medium_font = pygame.font.Font(None, 50); self.large_font = pygame.font.Font(None, 74)
        self.screen=pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT));pygame.display.set_caption("Cricket Match Animation");self.clock=pygame.time.Clock();
        # Initialize game components
        self.scoreboard = Scoreboard(self.font, SCREEN_WIDTH); self.current_score = 0; self.current_wickets = 0; self.total_balls_bowled_innings = 0
        self.game_state="menu";self.team_a=None;self.team_b=None;self.ball_log=[];self.bowler=None;self.batsman=None;self.ball=None;self.fielders=[];self.current_ball_index=0;self.animation_phase=ANIMATION_PHASE_PRE_BALL;self.inter_ball_pause_timer=0;self.inter_ball_pause_duration=FPS*2;self.current_outcome_display="";self.batsman_stumps_hit=False
        self.fielding_phase_timer=0;self.crowd=Crowd(pygame.Rect(0,0,SCREEN_WIDTH,CROWD_AREA_HEIGHT))

        # Load data if running in Pyodide and data is provided by Flask
        external_data_loaded=False
        if platform.system()=="Emscripten":
            try:
                match_data_js=js.globals.get('match_data_for_animation')
                if match_data_js:
                    match_data_py=match_data_js.to_py()
                    def hex_to_rgb(h):h=h.lstrip('#');return tuple(int(h[i:i+2],16)for i in(0,2,4))if len(h)==6 else(0,0,255) # Helper for color conversion
                    self.team_a=Team(match_data_py.get("team_a_name","Team A"),hex_to_rgb(match_data_py.get("team_a_color_hex","#0000FF")))
                    self.team_b=Team(match_data_py.get("team_b_name","Team B"),hex_to_rgb(match_data_py.get("team_b_color_hex","#FF0000")))
                    self.ball_log=match_data_py.get("log",[])
                    if not self.ball_log:self.ball_log=[0,1,4,"wicket",6,0,0,2,0,4,0,"wicket",0,1,0,6,0,0,2,0] # Default log if empty
                    if self.team_a and self.team_b and self.ball_log:
                        self.scoreboard.set_teams(self.team_a.name, self.team_b.name, self.team_a.name) # Setup scoreboard teams
                        self.game_state="animation"; external_data_loaded=True # Go directly to animation
            except Exception: pass # Ignore errors if Pyodide data access fails

        self.ui=UI(self) # Initialize UI (buttons, screens)

        if external_data_loaded: self.initialize_animation_elements() # Setup animation elements if data loaded

    # Sets initial positions for players and ball, resets stumps state.
    def set_player_positions(self,init_setup=False):
        self.batsman_stumps_hit=False;bats_clr = self.team_a.color if self.team_a else YELLOW;bowl_clr = self.team_b.color if self.team_b else BLUE
        bcr_y=STUMPS_LINE_Y_BOWLER+20; bx=PITCH_X+PITCH_WIDTH//2
        if not self.bowler:self.bowler=Bowler(bowl_clr,bx,bcr_y)
        self.bowler.reset_state(bcr_y);self.bowler.color=bowl_clr
        btsmn_x=PITCH_X+PITCH_WIDTH//2;btsmn_y=STUMPS_LINE_Y_BATSMAN-20
        if not self.batsman:self.batsman=Batsman(bats_clr,btsmn_x,btsmn_y)
        else:self.batsman.x,self.batsman.y,self.batsman.color=btsmn_x,btsmn_y,bats_clr; self.batsman.current_action="idle"; self.batsman.bat_angle=0
        if not self.ball:self.ball=Ball(self.bowler.x,self.bowler.y-self.bowler.radius-BALL_RADIUS)
        self.ball.x,self.ball.y=self.bowler.x,self.bowler.y-self.bowler.radius-BALL_RADIUS;self.ball.visible=True;self.ball.current_travel_frame=0; self.ball.has_bounced=False
        for fielder in self.fielders: fielder.reset_position() # Reset fielders to original positions
    # Initializes all elements needed for the animation state (players, fielders, scores).
    def initialize_animation_elements(self):
        self.set_player_positions(init_setup=True);bowl_clr = self.team_b.color if self.team_b else BLUE; self.fielders=[]
        # Define initial fielder positions
        f_pos=[(PITCH_X+PITCH_WIDTH//2,POPPING_CREASE_Y_BOWLER+60),(PITCH_X-100,PITCH_Y_BOWLER_END+150),(PITCH_X+PITCH_WIDTH+100,PITCH_Y_BOWLER_END+150),(PITCH_X-150,PITCH_Y_BATSMAN_END-150),(PITCH_X+PITCH_WIDTH+150,PITCH_Y_BATSMAN_END-150),(SCREEN_WIDTH//2,PITCH_Y_BATSMAN_END+100),(PITCH_X-200,SCREEN_HEIGHT//2+50),(PITCH_X+PITCH_WIDTH+200,SCREEN_HEIGHT//2+50),(SCREEN_WIDTH//2,PITCH_Y_BOWLER_END+PITCH_LENGTH+100)]
        min_yf=int(SCREEN_HEIGHT*0.20)+FIELDER_RADIUS+5;max_yf=SCREEN_HEIGHT-FIELDER_RADIUS-35 # Field boundaries
        for i in range(9):fx,fy=f_pos[i%len(f_pos)];fy=max(min_yf,min(fy,max_yf));fx=max(FIELDER_RADIUS+35,min(fx,SCREEN_WIDTH-FIELDER_RADIUS-35));self.fielders.append(Fielder(bowl_clr,fx,fy))
        # Reset game progress for animation
        self.current_ball_index=0;self.animation_phase=ANIMATION_PHASE_PRE_BALL;self.current_outcome_display=""
        self.current_score = 0; self.current_wickets = 0; self.total_balls_bowled_innings = 0
        batting_team_name_for_sb = self.team_a.name if self.team_a else "Batting Team"
        if self.team_a and self.team_b and not self.scoreboard.batting_team_name: self.scoreboard.set_teams(self.team_a.name, self.team_b.name, batting_team_name_for_sb)
        self.scoreboard.update(0, False, 0, 0, 0) # Initial scoreboard display
    # Resets state for a new ball delivery.
    def reset_for_new_ball(self):
        self.set_player_positions();outcome=self.ball_log[self.current_ball_index];self.current_outcome_display=f"Ball {self.current_ball_index+1}: {outcome}";self.animation_phase=ANIMATION_PHASE_BOWLER_RUNUP;self.ball.visible = True
    # Generates a sample ball-by-ball log for testing if no external log is provided.
    def generate_ball_log(self):
        log=[];chs=VALID_LOG_OUTCOMES;wts=[0.30,0.20,0.10,0.10,0.15,0.10,0.05];
        for _ in range(20):o=random.choices(chs,wts,k=1)[0];log.append(int(o) if o.isdigit() else o)
        return log
    # Main game loop, handles events, updates game state, and draws elements.
    def run(self):
        prev_st=self.game_state; is_direct_animation_mode = platform.system() == "Emscripten" and js.globals.get('match_data_for_animation') and self.bowler is not None
        # Event handling
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT:return False
            if not is_direct_animation_mode : self.ui.handle_event(ev) # Only process UI events if not in direct animation
        # State transition from UI to animation
        if prev_st!="animation" and self.game_state=="animation":
            if self.team_a and self.team_b and self.ball_log:
                if not self.bowler : self.initialize_animation_elements() # Initialize if not already done (e.g., by external data loading)
            elif not is_direct_animation_mode: self.game_state="log_input";self.ui.log_message_surf=self.font.render("Select teams and log first!",True,RED)

        self.screen.fill(SKY_BLUE) # Background
        if self.game_state == "animation":
            if self.crowd : self.crowd.update() # Update crowd animations

        # Draw based on game state
        if self.game_state=="menu":self.ui.draw_initial_screen()
        elif self.game_state=="team_selection":self.ui.draw_team_selection_screen()
        elif self.game_state=="log_input":self.ui.draw_log_input_screen()
        elif self.game_state=="animation":
            if not self.bowler: self.ui.draw_animation_scene(None, None, [], None, self.crowd, "Error: Match data missing.", False); # Failsafe draw
            else: # Normal animation drawing and state machine
                # Check for match completion
                if self.animation_phase!=ANIMATION_PHASE_MATCH_OVER and self.current_ball_index>=len(self.ball_log):
                    self.animation_phase=ANIMATION_PHASE_MATCH_OVER;self.current_outcome_display="Match Over!";
                    self.scoreboard.last_ball_outcome_display = "Match Over";
                    if self.crowd: self.crowd.set_reaction("match_over")

                # Animation State Machine
                if self.animation_phase==ANIMATION_PHASE_PRE_BALL:
                    if self.current_ball_index<len(self.ball_log):self.reset_for_new_ball()
                    else:self.animation_phase=ANIMATION_PHASE_MATCH_OVER;self.current_outcome_display="Match Over!"; self.scoreboard.last_ball_outcome_display="Match Over"
                elif self.animation_phase==ANIMATION_PHASE_BOWLER_RUNUP:
                    if self.bowler.update_runup(): self.ball.x=self.bowler.x; self.ball.y=self.bowler.y-self.bowler.radius-BALL_RADIUS # Ball follows bowler
                    else: self.animation_phase=ANIMATION_PHASE_BOWLER_ACTION
                elif self.animation_phase==ANIMATION_PHASE_BOWLER_ACTION:
                    if self.bowler.update_action(): # Bowler action in progress
                        if self.bowler.is_releasing_ball: # Moment of ball release
                            rx=self.bowler.x+self.bowler.radius*math.cos(math.radians(self.bowler.arm_angle));ry=self.bowler.y-self.bowler.radius*math.sin(math.radians(self.bowler.arm_angle));
                            bt_y=STUMPS_LINE_Y_BATSMAN;bpy=STUMPS_LINE_Y_BATSMAN-PITCH_BOUNCE_POINT_OFFSET;
                            self.ball.start_travel((rx,ry),(self.batsman.x,bt_y),bpy); self.animation_phase=ANIMATION_PHASE_BALL_TRAVEL
                        elif not (self.animation_phase == ANIMATION_PHASE_BALL_TRAVEL) :self.ball.x=self.bowler.x;self.ball.y=self.bowler.y-self.bowler.radius-BALL_RADIUS # Ball held until release
                    else: # Bowler action finished
                        if self.animation_phase!=ANIMATION_PHASE_BALL_TRAVEL: self.animation_phase=ANIMATION_PHASE_SHOWING_OUTCOME # Skip to outcome if ball not released
                elif self.animation_phase==ANIMATION_PHASE_BALL_TRAVEL:
                    if not self.ball.update_trajectory(): # Ball travel finished
                        current_outcome = self.ball_log[self.current_ball_index]; self.batsman.start_action(current_outcome)
                        if current_outcome == "wicket": self.batsman_stumps_hit = True; self.ball.x = self.batsman.x; self.ball.y = STUMPS_LINE_Y_BATSMAN + STUMP_HEIGHT/2; self.ball.visible = False
                        self.animation_phase = ANIMATION_PHASE_BATSMAN_ACTION
                elif self.animation_phase == ANIMATION_PHASE_BATSMAN_ACTION:
                    if not self.batsman.update_animation(): # Batsman animation finished
                        current_outcome = self.ball_log[self.current_ball_index]; self.total_balls_bowled_innings += 1
                        runs_on_this_ball = 0; is_wicket_this_ball = False
                        if isinstance(current_outcome, int): self.current_score += current_outcome; runs_on_this_ball = current_outcome
                        elif current_outcome == "wicket": self.current_wickets += 1; is_wicket_this_ball = True
                        self.scoreboard.update(runs_on_this_ball, is_wicket_this_ball, self.current_score, self.current_wickets, self.total_balls_bowled_innings)
                        if self.crowd: self.crowd.set_reaction(current_outcome)
                        # Trigger fielding for scoring shots (not wickets)
                        if isinstance(current_outcome, int) and current_outcome >= 0 and not is_wicket_this_ball:
                            fielders_to_move_indices = random.sample(range(len(self.fielders)), k=min(2, len(self.fielders)))
                            for i in fielders_to_move_indices: fielder = self.fielders[i]; target_x = fielder.original_x + random.randint(-25, 25); target_y = fielder.original_y + random.randint(-25, 25); target_x = max(FIELDER_RADIUS, min(target_x, SCREEN_WIDTH - FIELDER_RADIUS)); target_y = max(int(SCREEN_HEIGHT*0.20)+FIELDER_RADIUS, min(target_y, SCREEN_HEIGHT - FIELDER_RADIUS - 30)); fielder.start_move(target_x, target_y)
                            self.fielding_phase_timer = FIELDER_MAX_MOVE_FRAMES; self.animation_phase = ANIMATION_PHASE_FIELDING
                        else: self.animation_phase = ANIMATION_PHASE_SHOWING_OUTCOME # Wicket or non-fielding outcome
                elif self.animation_phase == ANIMATION_PHASE_FIELDING: # Fielders moving
                    still_fielders_moving = False
                    for fielder in self.fielders:
                        if fielder.is_moving:
                            if fielder.update_movement(): still_fielders_moving = True
                    self.fielding_phase_timer -=1
                    if not still_fielders_moving or self.fielding_phase_timer <=0: # Fielding animation time up or fielders stopped
                        for fielder in self.fielders: fielder.reset_position()
                        self.animation_phase = ANIMATION_PHASE_SHOWING_OUTCOME
                elif self.animation_phase==ANIMATION_PHASE_SHOWING_OUTCOME: # Brief pause to show outcome (implicitly handled by pause timer next)
                    self.inter_ball_pause_timer=self.inter_ball_pause_duration;self.animation_phase=ANIMATION_PHASE_PAUSED
                elif self.animation_phase==ANIMATION_PHASE_PAUSED: # Pause between balls
                    self.inter_ball_pause_timer-=1
                    if self.inter_ball_pause_timer<=0:
                        self.current_ball_index+=1 # Move to next ball
                        if self.current_ball_index<len(self.ball_log):self.animation_phase=ANIMATION_PHASE_PRE_BALL
                        else:self.animation_phase=ANIMATION_PHASE_MATCH_OVER;self.current_outcome_display="Match Over!"; self.scoreboard.last_ball_outcome_display="Match Over"; self.crowd.set_reaction("match_over")

                # Draw all animation elements
                self.ui.draw_animation_scene(self.bowler,self.batsman,self.fielders,self.ball,self.crowd, self.current_outcome_display,self.batsman_stumps_hit)
                self.scoreboard.draw(self.screen) # Draw scoreboard overlay
                # Draw team names overlay
                if self.team_a and self.team_b:teams_surf=self.font.render(f"{self.team_a.name}(Bat) vs {self.team_b.name}(Bowl)",True,BLACK);self.screen.blit(teams_surf,(10,10))

        # Draw other UI states if not in animation (menu, team select, log input)
        elif self.game_state=="menu":self.ui.draw_initial_screen()
        elif self.game_state=="team_selection":self.ui.draw_team_selection_screen()
        elif self.game_state=="log_input":self.ui.draw_log_input_screen()

        pygame.display.flip();self.clock.tick(FPS);return True

# Manages UI elements and screens for standalone mode.
class UI:
    def __init__(self, game): self.game=game;self.title_text=self.game.large_font.render("Cricket Match Animation",True,BLACK);self.title_rect=self.title_text.get_rect(center=(SCREEN_WIDTH//2,SCREEN_HEIGHT//4));self.start_button_rect=pygame.Rect(SCREEN_WIDTH//2-150,SCREEN_HEIGHT//2-25,300,50);self.start_button_text=self.game.font.render("Start Animated Match",True,BLACK);self.start_button_text_rect=self.start_button_text.get_rect(center=self.start_button_rect.center);self.sim_button_rect=pygame.Rect(SCREEN_WIDTH//2-150,SCREEN_HEIGHT//2+50,300,50);self.sim_button_text=self.game.font.render("Start Simulation Game",True,BLACK);self.sim_button_text_rect=self.sim_button_text.get_rect(center=self.sim_button_rect.center);self.available_teams=["India","Australia","England","Pakistan","South Africa","New Zealand"];self.selected_team_a_name=None;self.selected_team_b_name=None;self.team_option_height=40;self.team_option_width=200;self.team_a_options_rects=[];self.team_b_options_rects=[];self.select_team_a_text=self.game.medium_font.render("Select Team A (Batting)",True,BLACK);self.select_team_a_rect=self.select_team_a_text.get_rect(center=(SCREEN_WIDTH//4+50,SCREEN_HEIGHT//6));self.select_team_b_text=self.game.medium_font.render("Select Team B (Bowling)",True,BLACK);self.select_team_b_rect=self.select_team_b_text.get_rect(center=(SCREEN_WIDTH*3//4-50,SCREEN_HEIGHT//6));start_y_team=SCREEN_HEIGHT//6+60;
        for i,tn in enumerate(self.available_teams):rA=pygame.Rect(SCREEN_WIDTH//4-self.team_option_width//2+50,start_y_team+i*(self.team_option_height+10),self.team_option_width,self.team_option_height);self.team_a_options_rects.append(rA);rB=pygame.Rect(SCREEN_WIDTH*3//4-self.team_option_width//2-50,start_y_team+i*(self.team_option_height+10),self.team_option_width,self.team_option_height);self.team_b_options_rects.append(rB)
        self.confirm_teams_button_rect=pygame.Rect(SCREEN_WIDTH//2-100,SCREEN_HEIGHT-100,200,50);self.confirm_teams_button_text=self.game.font.render("Confirm Teams",True,BLACK);self.confirm_teams_button_text_rect=self.confirm_teams_button_text.get_rect(center=self.confirm_teams_button_rect.center);self.log_screen_title_text=self.game.medium_font.render("Provide Ball-by-Ball Log",True,BLACK);self.log_screen_title_rect=self.log_screen_title_text.get_rect(center=(SCREEN_WIDTH//2,SCREEN_HEIGHT//6));self.input_manual_log_button_rect=pygame.Rect(SCREEN_WIDTH//2-200,SCREEN_HEIGHT//4,400,50);self.input_manual_log_button_text=self.game.font.render("Input Manual Log",True,BLACK);self.input_manual_log_button_text_rect=self.input_manual_log_button_text.get_rect(center=self.input_manual_log_button_rect.center);self.simulate_match_button_rect=pygame.Rect(SCREEN_WIDTH//2-200,SCREEN_HEIGHT//4+60,400,50);self.simulate_match_button_text=self.game.font.render("Simulate 20-Ball Match",True,BLACK);self.simulate_match_button_text_rect=self.simulate_match_button_text.get_rect(center=self.simulate_match_button_rect.center);self.manual_log_input_rect=pygame.Rect(SCREEN_WIDTH//2-300,SCREEN_HEIGHT//2+20,600,50);self.manual_log_string="";self.log_input_active=False;self.max_log_chars=100;self.generated_log_display_surf=None;self.log_message_surf=None;self.start_animation_button_rect=pygame.Rect(SCREEN_WIDTH//2-150,SCREEN_HEIGHT-100,300,50);self.start_animation_button_text=self.game.font.render("Start Animation",True,BLACK);self.start_animation_button_text_rect=self.start_animation_button_text.get_rect(center=self.start_animation_button_rect.center)
    # Helper method to draw stumps.
    def draw_stumps(self,sfc,xc,yb,hit=False):st_px=[xc-STUMPS_GAP-STUMP_WIDTH//2,xc-STUMP_WIDTH//2,xc+STUMPS_GAP-STUMP_WIDTH//2];clr=STUMP_HIT_COLOR if hit else STUMP_COLOR;
        for sx in st_px:
            if hit and random.choice([True,False]):pygame.draw.line(sfc,clr,(sx,yb),(sx+random.randint(-5,5),yb-STUMP_HEIGHT-random.randint(0,10)),STUMP_WIDTH+1) # Scatter if hit
            else:pygame.draw.line(sfc,clr,(sx,yb),(sx,yb-STUMP_HEIGHT),STUMP_WIDTH)
    # Draws the main animation scene including ground, pitch, players, ball, and crowd.
    def draw_animation_scene(self, bowler, batsman, fielders, ball_obj, crowd_obj, current_outcome_text="", batsman_stumps_hit=False):
        # Draw static elements: crowd backdrop, outfield, pitch, creases, boundary
        crowd_backdrop_rect = pygame.Rect(0, 0, SCREEN_WIDTH, CROWD_AREA_HEIGHT); pygame.draw.rect(self.game.screen, CROWD_COLOR_PLACEHOLDER, crowd_backdrop_rect)
        if crowd_obj: crowd_obj.draw(self.game.screen) # Draw animated crowd
        outfield_rect = pygame.Rect(0, CROWD_AREA_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT - CROWD_AREA_HEIGHT); pygame.draw.rect(self.game.screen, GREEN, outfield_rect)
        pitch_rect = pygame.Rect(PITCH_X, PITCH_Y_BOWLER_END, PITCH_WIDTH, PITCH_LENGTH); pygame.draw.rect(self.game.screen, LIGHT_BROWN, pitch_rect)
        pc_bw=(PITCH_X-(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BOWLER);pc_be=(PITCH_X+PITCH_WIDTH+(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BOWLER);pygame.draw.line(self.game.screen,WHITE,pc_bw,pc_be,3);pc_bw2=(PITCH_X-(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BATSMAN);pc_be2=(PITCH_X+PITCH_WIDTH+(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BATSMAN);pygame.draw.line(self.game.screen,WHITE,pc_bw2,pc_be2,3);pygame.draw.line(self.game.screen,WHITE,(PITCH_X,STUMPS_LINE_Y_BOWLER),(PITCH_X+PITCH_WIDTH,STUMPS_LINE_Y_BOWLER),2);pygame.draw.line(self.game.screen,WHITE,(PITCH_X,STUMPS_LINE_Y_BATSMAN),(PITCH_X+PITCH_WIDTH,STUMPS_LINE_Y_BATSMAN),2);bm=30;dl=15;gl=10
        for x in range(bm,SCREEN_WIDTH-bm,dl+gl):pygame.draw.line(self.game.screen,WHITE,(x,SCREEN_HEIGHT-bm),(min(x+dl,SCREEN_WIDTH-bm),SCREEN_HEIGHT-bm),2)
        for y in range(int(CROWD_AREA_HEIGHT)+bm,SCREEN_HEIGHT-bm,dl+gl):pygame.draw.line(self.game.screen,WHITE,(bm,y),(bm,min(y+dl,SCREEN_HEIGHT-bm)),2);pygame.draw.line(self.game.screen,WHITE,(SCREEN_WIDTH-bm,y),(SCREEN_WIDTH-bm,min(y+dl,SCREEN_HEIGHT-bm)),2)
        # Draw stumps
        self.draw_stumps(self.game.screen,PITCH_X+PITCH_WIDTH//2,STUMPS_LINE_Y_BOWLER);self.draw_stumps(self.game.screen,PITCH_X+PITCH_WIDTH//2,STUMPS_LINE_Y_BATSMAN,batsman_stumps_hit)
        # Draw dynamic elements: players and ball
        if bowler:bowler.draw(self.game.screen);
        if batsman:batsman.draw(self.game.screen)
        for fielder in fielders:fielder.draw(self.game.screen)
        if ball_obj:ball_obj.draw(self.game.screen)
        # Draw text overlay for current ball outcome
        if current_outcome_text:status_surf=self.game.font.render(current_outcome_text,True,BLACK);status_rect=status_surf.get_rect(center=(SCREEN_WIDTH//2,SCREEN_HEIGHT*0.10));self.game.screen.blit(status_surf,status_rect)
    # Draws the initial menu screen.
    def draw_initial_screen(self):self.game.screen.blit(self.title_text,self.title_rect);pygame.draw.rect(self.game.screen,WHITE,self.start_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.start_button_rect,2);self.game.screen.blit(self.start_button_text,self.start_button_text_rect);pygame.draw.rect(self.game.screen,WHITE,self.sim_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.sim_button_rect,2);self.game.screen.blit(self.sim_button_text,self.sim_button_text_rect)
    # Draws the team selection screen.
    def draw_team_selection_screen(self):self.game.screen.blit(self.select_team_a_text,self.select_team_a_rect);self.game.screen.blit(self.select_team_b_text,self.select_team_b_rect)
        for i,team_name in enumerate(self.available_teams):
            rect_a=self.team_a_options_rects[i];color_a=WHITE;text_color_a=BLACK
            if team_name==self.selected_team_a_name:color_a=TEAM_COLORS.get(team_name,BLUE);text_color_a=WHITE if team_name!="Australia" else BLACK
            pygame.draw.rect(self.game.screen,color_a,rect_a);pygame.draw.rect(self.game.screen,BLACK,rect_a,2);tsa=self.game.font.render(team_name,True,text_color_a);self.game.screen.blit(tsa,tsa.get_rect(center=rect_a.center))
            rect_b=self.team_b_options_rects[i];color_b=WHITE;text_color_b=BLACK
            if team_name==self.selected_team_b_name:color_b=TEAM_COLORS.get(team_name,BLUE);text_color_b=WHITE if team_name!="Australia" else BLACK
            if self.selected_team_a_name==team_name and self.selected_team_a_name is not None and self.selected_team_b_name!=team_name:color_b=GREY;text_color_b=DARK_GREY
            pygame.draw.rect(self.game.screen,color_b,rect_b);pygame.draw.rect(self.game.screen,BLACK,rect_b,2);tsb=self.game.font.render(team_name,True,text_color_b);self.game.screen.blit(tsb,tsb.get_rect(center=rect_b.center))
        confirm_color=GREY if not(self.selected_team_a_name and self.selected_team_b_name and self.selected_team_a_name!=self.selected_team_b_name) else WHITE
        pygame.draw.rect(self.game.screen,confirm_color,self.confirm_teams_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.confirm_teams_button_rect,2);self.game.screen.blit(self.confirm_teams_button_text,self.confirm_teams_button_text_rect)
    # Draws the log input screen.
    def draw_log_input_screen(self):self.game.screen.blit(self.log_screen_title_text,self.log_screen_title_rect);pygame.draw.rect(self.game.screen,LIGHT_GREEN if self.log_input_active else WHITE,self.input_manual_log_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.input_manual_log_button_rect,2);self.game.screen.blit(self.input_manual_log_button_text,self.input_manual_log_button_text_rect);sim_color=LIGHT_GREEN if not self.log_input_active and self.generated_log_display_surf else WHITE;pygame.draw.rect(self.game.screen,sim_color,self.simulate_match_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.simulate_match_button_rect,2);self.game.screen.blit(self.simulate_match_button_text,self.simulate_match_button_text_rect);disp_y=self.manual_log_input_rect.top-30
        if self.log_input_active:pygame.draw.rect(self.game.screen,WHITE,self.manual_log_input_rect);pygame.draw.rect(self.game.screen,BLACK,self.manual_log_input_rect,2);lts=self.game.font.render(self.manual_log_string,True,BLACK);self.game.screen.blit(lts,(self.manual_log_input_rect.x+5,self.manual_log_input_rect.y+5));inst_s=self.game.font.render("Type comma-separated log (e.g., 0,1,wicket,4)",True,DARK_GREY);self.game.screen.blit(inst_s,(self.manual_log_input_rect.x,self.manual_log_input_rect.bottom+5))
        elif self.generated_log_display_surf:self.game.screen.blit(self.generated_log_display_surf,(SCREEN_WIDTH//2-self.generated_log_display_surf.get_width()//2,disp_y+40));inst_s=self.game.font.render("Simulated 20-Ball Log:",True,BLACK);self.game.screen.blit(inst_s,(SCREEN_WIDTH//2-inst_s.get_width()//2,disp_y))
        sa_color=WHITE if self.game.ball_log else GREY;pygame.draw.rect(self.game.screen,sa_color,self.start_animation_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.start_animation_button_rect,2);self.game.screen.blit(self.start_animation_button_text,self.start_animation_button_text_rect)
        if self.log_message_surf:self.game.screen.blit(self.log_message_surf,(SCREEN_WIDTH//2-self.log_message_surf.get_width()//2,self.start_animation_button_rect.top-40))
    # Validates and parses a comma-separated log string.
    def _validate_and_parse_log(self,log_string):self.log_message_surf=None;
        if not log_string.strip():self.log_message_surf=self.game.font.render("Manual log is empty.",True,RED);return[]
        items=[i.strip().lower() for i in log_string.split(',')];parsed_log=[]
        for i in items:
            if i in VALID_LOG_OUTCOMES:parsed_log.append(int(i) if i.isdigit() else i)
            else:self.log_message_surf=self.game.font.render(f"Invalid outcome: '{i}'. Use 0-6 or wicket.",True,RED);return[]
        if not parsed_log:self.log_message_surf=self.game.font.render("No valid outcomes found in log.",True,RED);return[]
        self.log_message_surf=self.game.font.render("Log parsed successfully!",True,GREEN);return parsed_log
    # Handles user input events for UI interactions.
    def handle_event(self,event):
        if self.game.game_state=="menu":
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                if self.start_button_rect.collidepoint(event.pos):self.game.game_state="team_selection"
                elif self.sim_button_rect.collidepoint(event.pos):self.game.game_state="team_selection"
        elif self.game.game_state=="team_selection": # ... (Team selection logic)
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                for i,r in enumerate(self.team_a_options_rects):
                    if r.collidepoint(event.pos):self.selected_team_a_name=self.available_teams[i];
                                                 if self.selected_team_b_name==self.selected_team_a_name:self.selected_team_b_name=None;return
                for i,r in enumerate(self.team_b_options_rects):
                    if r.collidepoint(event.pos):
                        name=self.available_teams[i]
                        if name!=self.selected_team_a_name:self.selected_team_b_name=name;return
                if self.confirm_teams_button_rect.collidepoint(event.pos) and self.selected_team_a_name and self.selected_team_b_name and self.selected_team_a_name!=self.selected_team_b_name:
                    # Create Team instances with colors (using default from TEAM_COLORS if not provided by Flask)
                    team_a_color = TEAM_COLORS.get(self.selected_team_a_name, BLUE)
                    team_b_color = TEAM_COLORS.get(self.selected_team_b_name, YELLOW)
                    self.game.team_a=Team(self.selected_team_a_name, team_a_color)
                    self.game.team_b=Team(self.selected_team_b_name, team_b_color)
                    # Update scoreboard with team names for standalone mode
                    self.game.scoreboard.set_teams(self.game.team_a.name, self.game.team_b.name, self.game.team_a.name)
                    self.game.game_state="log_input";self.manual_log_string="";self.game.ball_log=[];self.log_input_active=False;self.generated_log_display_surf=None;self.log_message_surf=None
        elif self.game.game_state=="log_input": # ... (Log input logic)
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                self.log_message_surf=None
                if self.input_manual_log_button_rect.collidepoint(event.pos):self.log_input_active=True;self.generated_log_display_surf=None;self.game.ball_log=[];self.manual_log_string=""
                elif self.simulate_match_button_rect.collidepoint(event.pos):
                    self.log_input_active=False;self.game.ball_log=self.game.generate_ball_log();ls=", ".join(map(str,self.game.ball_log));self.generated_log_display_surf=self.game.font.render(ls,True,BLACK);self.log_message_surf=self.game.font.render("Match simulated!",True,GREEN)
                elif self.start_animation_button_rect.collidepoint(event.pos):
                    if self.log_input_active:
                        pl=self._validate_and_parse_log(self.manual_log_string)
                        if pl:self.game.ball_log=pl
                        else:self.game.ball_log=[]
                    if self.game.ball_log:self.game.game_state="animation"
                    else:self.log_message_surf=self.game.font.render("Please input/simulate valid log.",True,RED)
            if self.log_input_active and event.type==pygame.KEYDOWN:
                if event.key==pygame.K_BACKSPACE:self.manual_log_string=self.manual_log_string[:-1]
                elif len(self.manual_log_string)<self.max_log_chars and(event.unicode.isalnum() or event.unicode==','):self.manual_log_string+=event.unicode
                self.game.ball_log=[]

# Placeholder for Scoreboard class if not defined above (though it is)
# class Scoreboard: pass
active_game = None
# Main asynchronous function to run the game, compatible with Pyodide.
async def main():
    global active_game; active_game = CricketGame();
    running = True
    while running:
        if active_game: running = active_game.run() # Run game logic and drawing
        # Yield control for other tasks in browser environment
        if platform.system() == "Emscripten": await asyncio.sleep(0)
        else: await asyncio.sleep(1.0 / FPS) # Standard desktop sleep
    pygame.quit() # Clean up Pygame resources when game loop ends

# Entry point for the script.
if __name__ == "__main__":
    if platform.system() == "Emscripten": # Running in Pyodide/browser
        asyncio.ensure_future(main())
    else: # Running as a standard Python script
        asyncio.run(main())

[end of IPL-3.0/static/animation/cricket_animation.py]
