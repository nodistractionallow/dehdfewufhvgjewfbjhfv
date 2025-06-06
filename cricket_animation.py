import asyncio
import platform
import pygame
import random
import math

# --- Constants ---
PLAYER_RADIUS = 15; FIELDER_RADIUS = 12; BALL_RADIUS = 5; FPS = 60; SCREEN_WIDTH = 1280; SCREEN_HEIGHT = 720
WHITE = (255,255,255); BLACK = (0,0,0); LIGHT_BROWN = (210,180,140); GREEN = (34,139,34)
RED = (255,0,0); BLUE = (0,0,255); YELLOW = (255,255,0); SKY_BLUE = (135,206,235)
GREY = (200,200,200); DARK_GREY = (100,100,100); CROWD_COLOR_PLACEHOLDER = (160,160,160)
STUMP_COLOR = (245, 245, 220)
STUMP_HIT_COLOR = (255, 69, 0)
TEAM_COLORS = {"India":BLUE,"Australia":YELLOW,"England":(200,0,0),"Pakistan":(0,128,0),"South Africa":(0,102,0),"New Zealand":BLACK}
VALID_LOG_OUTCOMES = ["0","1","2","3","4","6","wicket"]
PITCH_WIDTH = 60; PITCH_LENGTH = 400; PITCH_X = SCREEN_WIDTH//2-PITCH_WIDTH//2
PITCH_Y_BOWLER_END = SCREEN_HEIGHT*0.25; PITCH_Y_BATSMAN_END = PITCH_Y_BOWLER_END+PITCH_LENGTH
CREASE_LENGTH = PITCH_WIDTH+20; POPPING_CREASE_Y_BOWLER = int(PITCH_Y_BOWLER_END+PITCH_LENGTH*0.1)
POPPING_CREASE_Y_BATSMAN = int(PITCH_Y_BATSMAN_END-PITCH_LENGTH*0.1)
STUMPS_LINE_Y_BOWLER = int(PITCH_Y_BOWLER_END+PITCH_LENGTH*0.05)
STUMPS_LINE_Y_BATSMAN = int(PITCH_Y_BATSMAN_END-PITCH_LENGTH*0.05)
STUMP_HEIGHT = 25; STUMP_WIDTH = 3; STUMPS_GAP = 5

BOWLER_START_RUNUP_OFFSET = 80; BOWLER_RUNUP_FRAMES = 15; BOWLER_ACTION_FRAMES = 5*3
BALL_TRAVEL_TOTAL_FRAMES = 25; BALL_GRAVITY = 0.3; BALL_BOUNCE_FACTOR = -0.6
PITCH_BOUNCE_POINT_OFFSET = PITCH_LENGTH*0.25
BATSMAN_ACTION_TOTAL_FRAMES = 15

# Animation Phases
ANIMATION_PHASE_PRE_BALL="pre_ball";ANIMATION_PHASE_BOWLER_RUNUP="bowler_runup";ANIMATION_PHASE_BOWLER_ACTION="bowler_action"
ANIMATION_PHASE_BALL_TRAVEL="ball_travel";ANIMATION_PHASE_BATSMAN_ACTION="batsman_action"
ANIMATION_PHASE_SHOWING_OUTCOME="showing_outcome";ANIMATION_PHASE_PAUSED="paused";ANIMATION_PHASE_MATCH_OVER="match_over"


class Bowler:
    def __init__(self,c,x,y):self.color=c;self.initial_x=x;self.initial_y=y;self.x=x;self.y=y;self.radius=PLAYER_RADIUS;self.action_total_frames=BOWLER_ACTION_FRAMES;self.action_current_frame=0;self.runup_total_frames=BOWLER_RUNUP_FRAMES;self.runup_current_frame=0;self.start_runup_y=self.y-BOWLER_START_RUNUP_OFFSET;self.bowling_crease_y=self.y;self.arm_angle=0;self.is_releasing_ball=False
    def reset_state(self,bcy):self.x=self.initial_x;self.bowling_crease_y=bcy;self.start_runup_y=self.bowling_crease_y-BOWLER_START_RUNUP_OFFSET;self.y=self.start_runup_y;self.runup_current_frame=0;self.action_current_frame=0;self.arm_angle=0;self.is_releasing_ball=False
    def draw(self,s):pygame.draw.circle(s,self.color,(int(self.x),int(self.y)),self.radius);pygame.draw.circle(s,BLACK,(int(self.x),int(self.y)),self.radius,1);al=self.radius*1.5;ax=self.x+al*math.cos(math.radians(self.arm_angle));ay=self.y-al*math.sin(math.radians(self.arm_angle));pygame.draw.line(s,BLACK,(int(self.x),int(self.y)),(int(ax),int(ay)),4)
    def update_runup(self):
        if self.runup_current_frame<self.runup_total_frames:self.runup_current_frame+=1;p=self.runup_current_frame/self.runup_total_frames;self.y=self.start_runup_y+(self.bowling_crease_y-self.start_runup_y)*p;return True
        self.y=self.bowling_crease_y;return False
    def update_action(self):
        if self.action_current_frame<self.action_total_frames:
            self.action_current_frame+=1;pd=self.action_total_frames//5;cp=self.action_current_frame//pd
            if cp==0:self.arm_angle=45
            elif cp==1:self.arm_angle=90
            elif cp==2:self.arm_angle=135;self.is_releasing_ball=True
            elif cp==3:self.arm_angle=180;self.is_releasing_ball=False
            elif cp>=4:self.arm_angle=225
            return True
        self.is_releasing_ball=False;return False

class Batsman:
    def __init__(self, color, x, y):
        self.color = color; self.x = x; self.y = y; self.radius = PLAYER_RADIUS
        self.bat_width_orig = 8; self.bat_height_orig = 40; self.bat_color = (139,69,19)
        self.bat_rect = pygame.Rect(0,0,0,0)
        self.bat_angle = 0
        self.bat_draw_x_offset = self.radius

        self.action_frames_total = BATSMAN_ACTION_TOTAL_FRAMES
        self.action_current_frame = 0
        self.current_action = "idle"

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (self.x, self.y), self.radius)
        pygame.draw.circle(surface, BLACK, (self.x, self.y), self.radius, 1)

        bat_pivot_x = self.x + self.bat_draw_x_offset
        bat_pivot_y = self.y

        points = [
            (-self.bat_width_orig/2, -self.bat_height_orig/2), (self.bat_width_orig/2, -self.bat_height_orig/2),
            (self.bat_width_orig/2, self.bat_height_orig/2), (-self.bat_width_orig/2, self.bat_height_orig/2)
        ]

        rotated_points = []
        for px, py in points:
            rx = px * math.cos(math.radians(self.bat_angle)) - py * math.sin(math.radians(self.bat_angle))
            ry = px * math.sin(math.radians(self.bat_angle)) + py * math.cos(math.radians(self.bat_angle))
            rotated_points.append((bat_pivot_x + rx, bat_pivot_y + ry))

        pygame.draw.polygon(surface, self.bat_color, rotated_points)

    def start_action(self, outcome):
        self.action_current_frame = 0
        if isinstance(outcome, int):
            if outcome == 0: self.current_action = "defensive"
            elif outcome in [1,2,3]: self.current_action = "push"
            elif outcome == 4: self.current_action = "drive"
            elif outcome == 6: self.current_action = "six_swing"
        elif outcome == "wicket":
            self.current_action = "wicket_bowled"
        else: self.current_action = "idle"

        if self.current_action == "defensive" or self.current_action == "push": self.bat_angle = 0
        elif self.current_action == "drive": self.bat_angle = -15
        elif self.current_action == "six_swing": self.bat_angle = -45
        elif self.current_action == "wicket_bowled": self.bat_angle = 20
        else: self.bat_angle = 0

    def update_animation(self):
        if self.action_current_frame >= self.action_frames_total:
            self.current_action = "idle"; self.bat_angle = 0
            return False

        self.action_current_frame += 1
        progress = self.action_current_frame / self.action_frames_total

        if self.current_action == "defensive": self.bat_angle = 0
        elif self.current_action == "push": self.bat_angle = 10 * math.sin(progress * math.pi)
        elif self.current_action == "drive": self.bat_angle = -30 + 60 * math.sin(progress * math.pi)
        elif self.current_action == "six_swing": self.bat_angle = -60 + 90 * math.sin(progress * math.pi)
        elif self.current_action == "wicket_bowled": pass

        return True


class Ball:
    def __init__(self,x,y):self.initial_x=x;self.initial_y=y;self.x=x;self.y=y;self.radius=BALL_RADIUS;self.color=RED;self.visible=True;self.start_x,self.start_y=0,0;self.target_x,self.target_y=0,0;self.pitch_bounce_y_coord=0;self.vel_x,self.vel_y=0,0;self.gravity=BALL_GRAVITY;self.bounce_factor=BALL_BOUNCE_FACTOR;self.total_travel_frames=BALL_TRAVEL_TOTAL_FRAMES;self.current_travel_frame=0;self.has_bounced=False
    def draw(self,s):
        if self.visible:pygame.draw.circle(s,self.color,(int(self.x),int(self.y)),self.radius)
    def start_travel(self,sp,tp,pby):self.x,self.y=sp;self.start_x,self.start_y=sp;self.target_x,self.target_y=tp;self.pitch_bounce_y_coord=pby;self.current_travel_frame=0;self.has_bounced=False;self.visible=True;dx=self.target_x-self.start_x;ttba=self.total_travel_frames/2.2;self.vel_x=dx/self.total_travel_frames;self.vel_y=(self.pitch_bounce_y_coord-self.start_y-0.5*self.gravity*(ttba**2))/ttba;
                                     if self.vel_y > 0 and self.start_y < self.pitch_bounce_y_coord : self.vel_y *=-0.5;
                                     if self.vel_y == 0 : self.vel_y = -2
    def update_trajectory(self):
        if self.current_travel_frame>=self.total_travel_frames: self.visible=False; return False
        self.current_travel_frame+=1;self.x+=self.vel_x;self.y+=self.vel_y;self.vel_y+=self.gravity
        if not self.has_bounced and self.y>=self.pitch_bounce_y_coord:self.y=self.pitch_bounce_y_coord;self.vel_y*=self.bounce_factor;self.has_bounced=True
        if self.has_bounced and self.y>=self.target_y and self.vel_y > 0 : self.visible=False; return False
        if self.y > SCREEN_HEIGHT + self.radius : self.visible=False; return False
        if self.vel_y < 0 and self.y < PITCH_Y_BOWLER_END - self.radius*10: self.visible=False; return False
        return True

class Fielder:
    def __init__(self,c,x,y):self.color=c;self.x=x;self.y=y;self.radius=FIELDER_RADIUS
    def draw(self,s):pygame.draw.circle(s,self.color,(self.x,self.y),self.radius);pygame.draw.circle(s,BLACK,(self.x,self.y),self.radius,1)

class CricketGame:
    def __init__(self):
        self.screen=pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT));pygame.display.set_caption("Cricket Match Animation");self.clock=pygame.time.Clock();self.font=pygame.font.Font(None,36);self.medium_font=pygame.font.Font(None,50);self.large_font=pygame.font.Font(None,74);self.ui=UI(self);self.game_state="menu";self.team_a=None;self.team_b=None;self.ball_log=[];self.bowler=None;self.batsman=None;self.ball=None;self.fielders=[];self.current_ball_index=0;self.animation_phase=ANIMATION_PHASE_PRE_BALL;self.inter_ball_pause_timer=0;self.inter_ball_pause_duration=FPS*2;self.current_outcome_display=""
        self.batsman_stumps_hit = False

    def set_player_positions(self,init_setup=False):
        self.batsman_stumps_hit = False; bats_clr=self.team_a.color if self.team_a else YELLOW; bowl_clr=self.team_b.color if self.team_b else BLUE; bcr_y=STUMPS_LINE_Y_BOWLER+20; bx=PITCH_X+PITCH_WIDTH//2
        if not self.bowler:self.bowler=Bowler(bowl_clr,bx,bcr_y)
        self.bowler.reset_state(bcr_y);self.bowler.color=bowl_clr
        btsmn_x=PITCH_X+PITCH_WIDTH//2;btsmn_y=STUMPS_LINE_Y_BATSMAN-20
        if not self.batsman:self.batsman=Batsman(bats_clr,btsmn_x,btsmn_y)
        else:self.batsman.x,self.batsman.y,self.batsman.color=btsmn_x,btsmn_y,bats_clr; self.batsman.current_action="idle"; self.batsman.bat_angle=0
        if not self.ball:self.ball=Ball(self.bowler.x,self.bowler.y-self.bowler.radius-BALL_RADIUS)
        self.ball.x,self.ball.y=self.bowler.x,self.bowler.y-self.bowler.radius-BALL_RADIUS;self.ball.visible=True;self.ball.current_travel_frame=0

    def initialize_animation_elements(self):
        self.set_player_positions(init_setup=True);bowl_clr=self.team_b.color if self.team_b else BLUE;self.fielders=[]
        f_pos=[(PITCH_X+PITCH_WIDTH//2,POPPING_CREASE_Y_BOWLER+60),(PITCH_X-100,PITCH_Y_BOWLER_END+150),(PITCH_X+PITCH_WIDTH+100,PITCH_Y_BOWLER_END+150),(PITCH_X-150,PITCH_Y_BATSMAN_END-150),(PITCH_X+PITCH_WIDTH+150,PITCH_Y_BATSMAN_END-150),(SCREEN_WIDTH//2,PITCH_Y_BATSMAN_END+100),(PITCH_X-200,SCREEN_HEIGHT//2+50),(PITCH_X+PITCH_WIDTH+200,SCREEN_HEIGHT//2+50),(SCREEN_WIDTH//2,PITCH_Y_BOWLER_END+PITCH_LENGTH+100)]
        min_yf=int(SCREEN_HEIGHT*0.20)+FIELDER_RADIUS+5;max_yf=SCREEN_HEIGHT-FIELDER_RADIUS-35
        for i in range(9):fx,fy=f_pos[i%len(f_pos)];fy=max(min_yf,min(fy,max_yf));fx=max(FIELDER_RADIUS+35,min(fx,SCREEN_WIDTH-FIELDER_RADIUS-35));self.fielders.append(Fielder(bowl_clr,fx,fy))
        self.current_ball_index=0;self.animation_phase=ANIMATION_PHASE_PRE_BALL;self.current_outcome_display=""

    def reset_for_new_ball(self):
        print(f"Resetting for ball {self.current_ball_index+1}");self.set_player_positions();outcome=self.ball_log[self.current_ball_index];self.current_outcome_display=f"Ball {self.current_ball_index+1}: {outcome}";self.animation_phase=ANIMATION_PHASE_BOWLER_RUNUP

    def generate_ball_log(self):
        log=[];chs=VALID_LOG_OUTCOMES;wts=[0.30,0.20,0.10,0.10,0.15,0.10,0.05];
        for _ in range(20):o=random.choices(chs,wts,k=1)[0];log.append(int(o) if o.isdigit() else o)
        return log

    def run(self):
        prev_st=self.game_state;events = pygame.event.get();
        for ev in events:
            if ev.type==pygame.QUIT:return False
            self.ui.handle_event(ev)
        if prev_st!="animation" and self.game_state=="animation":
            if self.team_a and self.team_b and self.ball_log:self.initialize_animation_elements()
            else:print("Error: Anim start prereqs not met.");self.game_state="log_input";self.ui.log_message_surf=self.font.render("Select teams and log first!",True,RED)

        self.screen.fill(SKY_BLUE)
        if self.game_state=="menu":self.ui.draw_initial_screen()
        elif self.game_state=="team_selection":self.ui.draw_team_selection_screen()
        elif self.game_state=="log_input":self.ui.draw_log_input_screen()
        elif self.game_state=="animation":
            if self.animation_phase!=ANIMATION_PHASE_MATCH_OVER and self.current_ball_index>=len(self.ball_log):
                self.animation_phase=ANIMATION_PHASE_MATCH_OVER;self.current_outcome_display="Match Over!"

            if self.animation_phase==ANIMATION_PHASE_PRE_BALL:
                if self.current_ball_index<len(self.ball_log):self.reset_for_new_ball()
                else:self.animation_phase=ANIMATION_PHASE_MATCH_OVER;self.current_outcome_display="Match Over!"

            elif self.animation_phase==ANIMATION_PHASE_BOWLER_RUNUP:
                if self.bowler.update_runup():self.ball.x=self.bowler.x;self.ball.y=self.bowler.y-self.bowler.radius-BALL_RADIUS
                else:self.animation_phase=ANIMATION_PHASE_BOWLER_ACTION

            elif self.animation_phase==ANIMATION_PHASE_BOWLER_ACTION:
                if self.bowler.update_action():
                    if self.bowler.is_releasing_ball:
                        rx=self.bowler.x+self.bowler.radius*math.cos(math.radians(self.bowler.arm_angle));ry=self.bowler.y-self.bowler.radius*math.sin(math.radians(self.bowler.arm_angle))
                        bt_y=STUMPS_LINE_Y_BATSMAN;bpy=STUMPS_LINE_Y_BATSMAN-PITCH_BOUNCE_POINT_OFFSET
                        self.ball.start_travel((rx,ry),(self.batsman.x,bt_y),bpy)
                        self.animation_phase=ANIMATION_PHASE_BALL_TRAVEL
                    elif not (self.animation_phase == ANIMATION_PHASE_BALL_TRAVEL) :self.ball.x=self.bowler.x;self.ball.y=self.bowler.y-self.bowler.radius-BALL_RADIUS
                else:
                    if self.animation_phase!=ANIMATION_PHASE_BALL_TRAVEL:
                        self.animation_phase=ANIMATION_PHASE_SHOWING_OUTCOME

            elif self.animation_phase==ANIMATION_PHASE_BALL_TRAVEL:
                if not self.ball.update_trajectory():
                    current_outcome = self.ball_log[self.current_ball_index]
                    self.batsman.start_action(current_outcome)
                    if current_outcome == "wicket":
                        self.batsman_stumps_hit = True
                        self.ball.x = self.batsman.x
                        self.ball.y = STUMPS_LINE_Y_BATSMAN + STUMP_HEIGHT / 2
                        self.ball.visible = False
                    self.animation_phase = ANIMATION_PHASE_BATSMAN_ACTION

            elif self.animation_phase == ANIMATION_PHASE_BATSMAN_ACTION:
                if not self.batsman.update_animation():
                    self.animation_phase = ANIMATION_PHASE_SHOWING_OUTCOME

            elif self.animation_phase==ANIMATION_PHASE_SHOWING_OUTCOME:
                self.inter_ball_pause_timer=self.inter_ball_pause_duration;self.animation_phase=ANIMATION_PHASE_PAUSED

            elif self.animation_phase==ANIMATION_PHASE_PAUSED:
                self.inter_ball_pause_timer-=1
                if self.inter_ball_pause_timer<=0:
                    self.current_ball_index+=1
                    if self.current_ball_index<len(self.ball_log):self.animation_phase=ANIMATION_PHASE_PRE_BALL
                    else:self.animation_phase=ANIMATION_PHASE_MATCH_OVER;self.current_outcome_display="Match Over!"

            self.ui.draw_animation_scene(self.bowler,self.batsman,self.fielders,self.ball,self.current_outcome_display, self.batsman_stumps_hit)
            if self.team_a and self.team_b:teams_surf=self.font.render(f"{self.team_a.name}(Bat) vs {self.team_b.name}(Bowl)",True,BLACK);self.screen.blit(teams_surf,(10,10))

        pygame.display.flip();self.clock.tick(FPS);return True

class UI:
    def __init__(self, game): self.game=game;self.title_text=self.game.large_font.render("Cricket Match Animation",True,BLACK);self.title_rect=self.title_text.get_rect(center=(SCREEN_WIDTH//2,SCREEN_HEIGHT//4));self.start_button_rect=pygame.Rect(SCREEN_WIDTH//2-150,SCREEN_HEIGHT//2-25,300,50);self.start_button_text=self.game.font.render("Start Animated Match",True,BLACK);self.start_button_text_rect=self.start_button_text.get_rect(center=self.start_button_rect.center);self.sim_button_rect=pygame.Rect(SCREEN_WIDTH//2-150,SCREEN_HEIGHT//2+50,300,50);self.sim_button_text=self.game.font.render("Start Simulation Game",True,BLACK);self.sim_button_text_rect=self.sim_button_text.get_rect(center=self.sim_button_rect.center);self.available_teams=["India","Australia","England","Pakistan","South Africa","New Zealand"];self.selected_team_a_name=None;self.selected_team_b_name=None;self.team_option_height=40;self.team_option_width=200;self.team_a_options_rects=[];self.team_b_options_rects=[];self.select_team_a_text=self.game.medium_font.render("Select Team A (Batting)",True,BLACK);self.select_team_a_rect=self.select_team_a_text.get_rect(center=(SCREEN_WIDTH//4+50,SCREEN_HEIGHT//6));self.select_team_b_text=self.game.medium_font.render("Select Team B (Bowling)",True,BLACK);self.select_team_b_rect=self.select_team_b_text.get_rect(center=(SCREEN_WIDTH*3//4-50,SCREEN_HEIGHT//6));start_y_team=SCREEN_HEIGHT//6+60;
        for i,tn in enumerate(self.available_teams):rA=pygame.Rect(SCREEN_WIDTH//4-self.team_option_width//2+50,start_y_team+i*(self.team_option_height+10),self.team_option_width,self.team_option_height);self.team_a_options_rects.append(rA);rB=pygame.Rect(SCREEN_WIDTH*3//4-self.team_option_width//2-50,start_y_team+i*(self.team_option_height+10),self.team_option_width,self.team_option_height);self.team_b_options_rects.append(rB)
        self.confirm_teams_button_rect=pygame.Rect(SCREEN_WIDTH//2-100,SCREEN_HEIGHT-100,200,50);self.confirm_teams_button_text=self.game.font.render("Confirm Teams",True,BLACK);self.confirm_teams_button_text_rect=self.confirm_teams_button_text.get_rect(center=self.confirm_teams_button_rect.center);self.log_screen_title_text=self.game.medium_font.render("Provide Ball-by-Ball Log",True,BLACK);self.log_screen_title_rect=self.log_screen_title_text.get_rect(center=(SCREEN_WIDTH//2,SCREEN_HEIGHT//6));self.input_manual_log_button_rect=pygame.Rect(SCREEN_WIDTH//2-200,SCREEN_HEIGHT//4,400,50);self.input_manual_log_button_text=self.game.font.render("Input Manual Log",True,BLACK);self.input_manual_log_button_text_rect=self.input_manual_log_button_text.get_rect(center=self.input_manual_log_button_rect.center);self.simulate_match_button_rect=pygame.Rect(SCREEN_WIDTH//2-200,SCREEN_HEIGHT//4+60,400,50);self.simulate_match_button_text=self.game.font.render("Simulate 20-Ball Match",True,BLACK);self.simulate_match_button_text_rect=self.simulate_match_button_text.get_rect(center=self.simulate_match_button_rect.center);self.manual_log_input_rect=pygame.Rect(SCREEN_WIDTH//2-300,SCREEN_HEIGHT//2+20,600,50);self.manual_log_string="";self.log_input_active=False;self.max_log_chars=100;self.generated_log_display_surf=None;self.log_message_surf=None;self.start_animation_button_rect=pygame.Rect(SCREEN_WIDTH//2-150,SCREEN_HEIGHT-100,300,50);self.start_animation_button_text=self.game.font.render("Start Animation",True,BLACK);self.start_animation_button_text_rect=self.start_animation_button_text.get_rect(center=self.start_animation_button_rect.center)

    def draw_stumps(self, surface, x_center, y_base, hit=False):
        stump_positions_x = [x_center - STUMPS_GAP - STUMP_WIDTH//2, x_center - STUMP_WIDTH//2, x_center + STUMPS_GAP - STUMP_WIDTH//2]
        color = STUMP_HIT_COLOR if hit else STUMP_COLOR
        for sx in stump_positions_x:
            if hit and random.choice([True, False]):
                 pygame.draw.line(surface, color, (sx, y_base),(sx + random.randint(-5,5), y_base - STUMP_HEIGHT - random.randint(0,10)), STUMP_WIDTH+1)
            else:
                 pygame.draw.line(surface, color, (sx, y_base), (sx, y_base - STUMP_HEIGHT), STUMP_WIDTH)

    def draw_animation_scene(self, bowler, batsman, fielders, ball_obj, current_outcome_text="", batsman_stumps_hit=False):
        crowd_h=SCREEN_HEIGHT*0.2;pygame.draw.rect(self.game.screen,CROWD_COLOR_PLACEHOLDER,pygame.Rect(0,0,SCREEN_WIDTH,crowd_h));pygame.draw.rect(self.game.screen,GREEN,pygame.Rect(0,crowd_h,SCREEN_WIDTH,SCREEN_HEIGHT-crowd_h));pygame.draw.rect(self.game.screen,LIGHT_BROWN,pygame.Rect(PITCH_X,PITCH_Y_BOWLER_END,PITCH_WIDTH,PITCH_LENGTH));pc_bw=(PITCH_X-(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BOWLER);pc_be=(PITCH_X+PITCH_WIDTH+(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BOWLER);pygame.draw.line(self.game.screen,WHITE,pc_bw,pc_be,3);pc_bw2=(PITCH_X-(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BATSMAN);pc_be2=(PITCH_X+PITCH_WIDTH+(CREASE_LENGTH-PITCH_WIDTH)//2,POPPING_CREASE_Y_BATSMAN);pygame.draw.line(self.game.screen,WHITE,pc_bw2,pc_be2,3);pygame.draw.line(self.game.screen,WHITE,(PITCH_X,STUMPS_LINE_Y_BOWLER),(PITCH_X+PITCH_WIDTH,STUMPS_LINE_Y_BOWLER),2);pygame.draw.line(self.game.screen,WHITE,(PITCH_X,STUMPS_LINE_Y_BATSMAN),(PITCH_X+PITCH_WIDTH,STUMPS_LINE_Y_BATSMAN),2);bm=30;dl=15;gl=10
        for x in range(bm,SCREEN_WIDTH-bm,dl+gl):pygame.draw.line(self.game.screen,WHITE,(x,SCREEN_HEIGHT-bm),(min(x+dl,SCREEN_WIDTH-bm),SCREEN_HEIGHT-bm),2)
        for y in range(int(crowd_h)+bm,SCREEN_HEIGHT-bm,dl+gl):pygame.draw.line(self.game.screen,WHITE,(bm,y),(bm,min(y+dl,SCREEN_HEIGHT-bm)),2);pygame.draw.line(self.game.screen,WHITE,(SCREEN_WIDTH-bm,y),(SCREEN_WIDTH-bm,min(y+dl,SCREEN_HEIGHT-bm)),2)

        self.draw_stumps(self.game.screen, PITCH_X + PITCH_WIDTH // 2, STUMPS_LINE_Y_BOWLER)
        self.draw_stumps(self.game.screen, PITCH_X + PITCH_WIDTH // 2, STUMPS_LINE_Y_BATSMAN, batsman_stumps_hit)

        if bowler:bowler.draw(self.game.screen)
        if batsman:batsman.draw(self.game.screen)
        for fielder in fielders:fielder.draw(self.game.screen)
        if ball_obj:ball_obj.draw(self.game.screen)
        if current_outcome_text:status_surf=self.game.font.render(current_outcome_text,True,BLACK);status_rect=status_surf.get_rect(center=(SCREEN_WIDTH//2,SCREEN_HEIGHT*0.10));self.game.screen.blit(status_surf,status_rect)

    def draw_initial_screen(self):self.game.screen.blit(self.title_text,self.title_rect);pygame.draw.rect(self.game.screen,WHITE,self.start_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.start_button_rect,2);self.game.screen.blit(self.start_button_text,self.start_button_text_rect);pygame.draw.rect(self.game.screen,WHITE,self.sim_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.sim_button_rect,2);self.game.screen.blit(self.sim_button_text,self.sim_button_text_rect)
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
    def draw_log_input_screen(self):self.game.screen.blit(self.log_screen_title_text,self.log_screen_title_rect);pygame.draw.rect(self.game.screen,LIGHT_GREEN if self.log_input_active else WHITE,self.input_manual_log_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.input_manual_log_button_rect,2);self.game.screen.blit(self.input_manual_log_button_text,self.input_manual_log_button_text_rect);sim_color=LIGHT_GREEN if not self.log_input_active and self.generated_log_display_surf else WHITE;pygame.draw.rect(self.game.screen,sim_color,self.simulate_match_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.simulate_match_button_rect,2);self.game.screen.blit(self.simulate_match_button_text,self.simulate_match_button_text_rect);disp_y=self.manual_log_input_rect.top-30
        if self.log_input_active:pygame.draw.rect(self.game.screen,WHITE,self.manual_log_input_rect);pygame.draw.rect(self.game.screen,BLACK,self.manual_log_input_rect,2);lts=self.game.font.render(self.manual_log_string,True,BLACK);self.game.screen.blit(lts,(self.manual_log_input_rect.x+5,self.manual_log_input_rect.y+5));inst_s=self.game.font.render("Type comma-separated log (e.g., 0,1,wicket,4)",True,DARK_GREY);self.game.screen.blit(inst_s,(self.manual_log_input_rect.x,self.manual_log_input_rect.bottom+5))
        elif self.generated_log_display_surf:self.game.screen.blit(self.generated_log_display_surf,(SCREEN_WIDTH//2-self.generated_log_display_surf.get_width()//2,disp_y+40));inst_s=self.game.font.render("Simulated 20-Ball Log:",True,BLACK);self.game.screen.blit(inst_s,(SCREEN_WIDTH//2-inst_s.get_width()//2,disp_y))
        sa_color=WHITE if self.game.ball_log else GREY;pygame.draw.rect(self.game.screen,sa_color,self.start_animation_button_rect);pygame.draw.rect(self.game.screen,BLACK,self.start_animation_button_rect,2);self.game.screen.blit(self.start_animation_button_text,self.start_animation_button_text_rect)
        if self.log_message_surf:self.game.screen.blit(self.log_message_surf,(SCREEN_WIDTH//2-self.log_message_surf.get_width()//2,self.start_animation_button_rect.top-40))
    def _validate_and_parse_log(self,log_string):self.log_message_surf=None;
        if not log_string.strip():self.log_message_surf=self.game.font.render("Manual log is empty.",True,RED);return[]
        items=[i.strip().lower() for i in log_string.split(',')];parsed_log=[]
        for i in items:
            if i in VALID_LOG_OUTCOMES:parsed_log.append(int(i) if i.isdigit() else i)
            else:self.log_message_surf=self.game.font.render(f"Invalid outcome: '{i}'. Use 0-6 or wicket.",True,RED);return[]
        if not parsed_log:self.log_message_surf=self.game.font.render("No valid outcomes found in log.",True,RED);return[]
        self.log_message_surf=self.game.font.render("Log parsed successfully!",True,GREEN);return parsed_log
    def handle_event(self,event):
        if self.game.game_state=="menu":
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                if self.start_button_rect.collidepoint(event.pos):self.game.game_state="team_selection"
                elif self.sim_button_rect.collidepoint(event.pos):self.game.game_state="team_selection"
        elif self.game.game_state=="team_selection":
            if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                for i,r in enumerate(self.team_a_options_rects):
                    if r.collidepoint(event.pos):self.selected_team_a_name=self.available_teams[i];
                                                 if self.selected_team_b_name==self.selected_team_a_name:self.selected_team_b_name=None;return
                for i,r in enumerate(self.team_b_options_rects):
                    if r.collidepoint(event.pos):
                        name=self.available_teams[i]
                        if name!=self.selected_team_a_name:self.selected_team_b_name=name;return
                if self.confirm_teams_button_rect.collidepoint(event.pos) and self.selected_team_a_name and self.selected_team_b_name and self.selected_team_a_name!=self.selected_team_b_name:
                    self.game.team_a=Team(self.selected_team_a_name,TEAM_COLORS.get(self.selected_team_a_name,BLUE));self.game.team_b=Team(self.selected_team_b_name,TEAM_COLORS.get(self.selected_team_b_name,YELLOW))
                    self.game.game_state="log_input";self.manual_log_string="";self.game.ball_log=[];self.log_input_active=False;self.generated_log_display_surf=None;self.log_message_surf=None
        elif self.game.game_state=="log_input":
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

class Team:
    def __init__(self, name, color): self.name=name; self.color=color
class Crowd: pass
class Scoreboard: pass

active_game = None
async def main():
    global active_game; pygame.init(); pygame.font.init(); active_game = CricketGame(); running = True
    while running:
        if active_game: running = active_game.run()
        if platform.system() == "Emscripten": await asyncio.sleep(0)
        else: await asyncio.sleep(1.0 / FPS)
    pygame.quit()
if __name__ == "__main__":
    if platform.system() == "Emscripten": asyncio.ensure_future(main())
    else: asyncio.run(main())
