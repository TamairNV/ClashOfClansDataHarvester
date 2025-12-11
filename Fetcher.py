# Fetcher.py
from datetime import datetime
from os import environ
import urllib.parse
import dotenv
import requests
from DBManager import DBManager
import os



class FetchSession:


    def __init__(self, token=None, email=None, password=None):
        self.URL = "https://api.clashofclans.com/v1/"
        self.email = email
        self.password = password

        # Load initial token
        if token:
            self.TOKEN = token
        else:
            dotenv.load_dotenv()
            self.TOKEN = environ.get("TOKEN")

        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.TOKEN}"
        }

        host = environ.get("DB_HOST")
        password_db = environ.get("DB_PASSWORD")
        user = environ.get("DB_USER")
        DB = environ.get("DB_NAME")

        self.db = DBManager(host, user, password_db, DB)

    def getData(self, endpoint, retry=True):  # Add retry=True
        data = None
        try:
            encoded_tag = urllib.parse.quote(endpoint)
            URL = f"https://api.clashofclans.com/v1/{encoded_tag}"
            response = requests.get(URL, headers=self.headers)


            if response.status_code == 403 and retry and self.email and self.password:
                print(f"!! 403 Forbidden. IP changed. Refreshing Token...")
                try:
                    from tracker import get_valid_token  # Import here to avoid circular imports
                    new_token = get_valid_token()
                    self.TOKEN = new_token
                    self.headers["Authorization"] = f"Bearer {self.TOKEN}"
                    return self.getData(endpoint, retry=False)  # Recursive Retry
                except Exception as e:
                    print(f"CRITICAL: Token refresh failed: {e}")

            if response.status_code == 200:
                data = response.json()
            else:
                print(f"Error fetching data. Status code: {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")

        return data

    def getPlayerData(self):
        pass

    def getClanData(self):
        pass


def fillLeagueTable(session):
    data = session.getData(f"leaguetiers")['items']
    for league in data:
        sql = """
        INSERT IGNORE INTO League (name, iconURL) VALUES (?,?)
        """

        session.db.execute(sql, (league['name'], league['iconUrls']['small'],))



class clan:
    def __init__(self,tag,session):
        self.session = session
        self.data = session.getData(f"clans/{tag}")
        self.name = self.data['name']
        self.clanTag = self.data['tag']
        self.level = self.data['clanLevel']
        self.saveClanData()

        self.saveClanMemberData()

    def saveClanData(self):
        sql = """
        SELECT tag FROM Clan WHERE tag = ?;
        """
        clans = self.session.db.execute(sql,(self.clanTag,))
        if not clans:
            sql = """
            INSERT IGNORE INTO Clan(tag,name,level) Values(?,?,?)
            """
            self.session.db.execute(sql, (self.clanTag,self.name,self.level))


    def saveClanMemberData(self):
        self.players = []
        for m in self.data['memberList']:
            self.players.append(player(m['tag'],self.session))

    def savePlayersSnapshot(self):  # run every half hour

        fresh_data = self.session.getData(f"clans/{self.clanTag}")


        if fresh_data:

            current_member_tags = [m['tag'] for m in fresh_data.get('memberList', [])]

            if len(current_member_tags) == 0:
                print(f"!! Warning: API returned 0 members for {self.name}. Skipping cleanup to be safe.")
                return

            sql_check = "SELECT playerTag FROM Player WHERE clanTag = ?"
            db_members = self.session.db.execute(sql_check, (self.clanTag,))

            db_member_tags = [row[0] for row in db_members]

            for db_tag in db_member_tags:
                if db_tag not in current_member_tags:
                    print(f"-> Player {db_tag} has LEFT/KICKED. Updating DB...")
                    # Remove them from the clan in the DB so we don't track them anymore
                    update_sql = "UPDATE Player SET clanTag = NULL WHERE playerTag = ?"
                    self.session.db.execute(update_sql, (db_tag,))


            self.players = []

            for m in fresh_data.get('memberList', []):
                p_obj = player(m['tag'], self.session)
                self.players.append(p_obj)
                p_obj.snapshot = p_obj.getNewSnapshot()


    def savePlayersActivity(self): # run every 10 mins
        for p in self.players:
            p.activityCheck()


class clanWar: # run every 30 mins

    def __init__(self,session,tag):
        self.session = session
        self.data = session.getData(f"clans/{tag}/currentwar")

        # 1. Check State First


        if not self.data:
            print(f"!! War Data missing for {tag} (API Error/403). Skipping.")
            return  # Stop processing immediately
        self.state = self.data.get('state')
        if self.state == 'notInWar':
            print("Clan is not in war.")
            return


        self.clanTag1 = tag
        self.clanTag2 = self.data['opponent']['tag']

        # If clanTag1 failed to load earlier, this saves it now so the War doesn't crash.
        check_sql = "SELECT tag FROM Clan WHERE tag = ?"
        if not self.session.db.execute(check_sql, (self.clanTag1,)):

            my_name = self.data['clan']['name']
            my_level = self.data['clan']['clanLevel']
            insert_sql = "INSERT IGNORE INTO Clan(tag, name, level) VALUES(?, ?, ?)"
            self.session.db.execute(insert_sql, (self.clanTag1, my_name, my_level))


        opp_name = self.data['opponent']['name']
        opp_level = self.data['opponent']['clanLevel']
        check_sql = "SELECT tag FROM Clan WHERE tag = ?"
        if not self.session.db.execute(check_sql, (self.clanTag2,)):
            insert_sql = "INSERT IGNORE INTO Clan(tag, name, level) VALUES(?, ?, ?)"
            self.session.db.execute(insert_sql, (self.clanTag2, opp_name, opp_level))


        self.teamSize = self.data['teamSize']
        self.startTime = self.data['startTime']
        self.endTime = self.data['endTime']
        self.warType = "Standard"
        self.leagueGroupID = None
        self.league = None
        self.id = None;

        self.saveWar()
        for m in self.data['opponent']['members']:
            player = warPlayer(m,self.clanTag2)
            player.savePlayer(self.session,self)

        for m in self.data['clan']['members']:
            player = warPlayer(m,self.clanTag1)
            player.savePlayer(self.session, self)


    def saveWar(self):
        def fix_time(t):
            if not t: return None
            try:
                # Parse the "YYYYMMDDTHHMMSS.000Z" format
                dt = datetime.strptime(t, "%Y%m%dT%H%M%S.%fZ")
                return dt
            except ValueError:
                return None

        sql = """
        SELECT warID FROM ClanWar WHERE (clanTag1 = ? AND clanTag2 = ?) AND state IN ('preparation', 'inWar');
        """

        wars = self.session.db.execute(sql,(self.clanTag1,self.clanTag2,))
        if not wars:
            sql = """
            INSERT IGNORE INTO ClanWar(clanTag1,clanTag2,state,teamSize,startTime,endTime,warType,leagueGroupId,league) Values(?,?,?,?,?,?,?,?,?)
            """

            self.session.db.execute(sql, (self.clanTag1, self.clanTag2, self.state, self.teamSize, fix_time(self.startTime),
                                          fix_time(self.endTime), self.warType, self.leagueGroupID, self.league))
            id = self.session.db.execute("SELECT LAST_INSERT_ID();")
            self.id = id[0][0]

        else:
            self.id = wars[0][0]
            update_sql = "UPDATE ClanWar SET state = ? WHERE warID = ?"
            self.session.db.execute(update_sql, (self.state, self.id))



class warResults: # run every 5 minutes

    @staticmethod
    def checkWarEnded(session):
        sql = """
        SELECT warID,clanTag1,clanTag2 FROM ClanWar WHERE state = "warEnded";
        """
        wars = session.db.execute(sql)

        if wars:
            for war in wars:
                check_sql = "SELECT 1 FROM WarResults WHERE warID = ?"
                exists = session.db.execute(check_sql, (war[0],))

                if not exists:
                    sql = """
                    SELECT a.stars, a.destruction, p.clanTag 
                    FROM Attack a
                    JOIN WarPlayer p ON a.attackerTag = p.playerTag AND a.warID = p.warID
                    WHERE a.warID = ?
                    """
                    attacks = session.db.execute(sql,(war[0],))
                    stars = [0,0]
                    destruction = [0,0]
                    numOfAttacks = [0,0]

                    for attack in attacks:
                        if attack[2] == war[1]:
                            stars[0] += attack[0]
                            destruction[0] += attack[1]
                            numOfAttacks[0] +=1
                        else:
                            stars[1] += attack[0]
                            destruction[1] += attack[1]
                            numOfAttacks[1] +=1

                    if numOfAttacks[0] > 0:
                        destruction[0] /= numOfAttacks[0]
                    if numOfAttacks[1] > 0:
                        destruction[1] /= numOfAttacks[1]

                    sql = """
                            INSERT  IGNORE INTO WarResults (warID, clanTag, totalDestruction, totalStars, result)
                            VALUES (?, ?, ?, ?, ?)
                            """
                    states = [None,None]
                    if stars[0] > stars[1]:
                        states[0] = "WIN"
                        states[1] = "LOSS"

                    elif stars[0] < stars[1]:
                        states[0] = "LOSS"
                        states[1] = "WIN"

                    elif destruction[0] > destruction[1]:
                        states[0] = "WIN"
                        states[1] = "LOSS"

                    elif destruction[0] < destruction[1]:
                        states[0] = "LOSS"
                        states[1] = "WIN"
                    else:
                        states[0] = "DRAW"
                        states[1] = "DRAW"


                    session.db.execute(sql,(war[0],war[1],destruction[0],stars[0],states[0]))
                    session.db.execute(sql, (war[0], war[2], destruction[1], stars[1], states[1]))

class warPlayer:
    def __init__(self,data,clanTag):
        self.playerTag = data['tag']
        self.mapPosition = data['mapPosition']
        self.townHallLevel = data['townhallLevel']
        self.name = data['name']
        self.clanTag = clanTag

    def savePlayer(self,session,war):
        sql = """
        INSERT IGNORE INTO WarPlayer (warID,playerTag,mapPosition,townHallLevel,name,clanTag) VALUES (?,?,?,?,?,?)
        """
        session.db.execute(sql,(war.id, self.playerTag,self.mapPosition,self.townHallLevel,self.name,self.clanTag,))


class attack: # run every 10 minutes

    @staticmethod
    def saveAttacks(session):
        sql = """
        SELECT warID,clanTag1,clanTag2 FROM ClanWar WHERE state = "inWar" OR state = "warEnded";
        """
        wars = session.db.execute(sql)

        if wars:
            for war in wars:
                data = session.getData(f"clans/{war[1]}/currentwar")

                for m in data['opponent']['members']:
                    for attack in m.get('attacks', []):

                        check_sql = "SELECT 1 FROM Attack WHERE warID=? AND attackerTag=? AND defenderTag=?"
                        exists = session.db.execute(check_sql, (war[0], attack['attackerTag'], attack['defenderTag']))

                        if not exists:

                            sql = """
                                INSERT IGNORE INTO Attack (warID, attackerTag, defenderTag, stars, destruction, startTime, duration)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """

                            session.db.execute(sql, (war[0],attack['attackerTag'],attack['defenderTag'],attack['stars'],attack['destructionPercentage'],datetime.now(),attack['duration']
                            ))
                for m in data['clan']['members']:
                    for attack in m.get('attacks', []):
                        check_sql = "SELECT 1 FROM Attack WHERE warID=? AND attackerTag=? AND defenderTag=?"
                        exists = session.db.execute(check_sql, (war[0], attack['attackerTag'], attack['defenderTag']))

                        if not exists:

                            sql = """
                            INSERT IGNORE INTO Attack (warID, attackerTag, defenderTag, stars, destruction, startTime, duration)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """

                            session.db.execute(sql, (war[0],attack['attackerTag'],attack['defenderTag'],attack['stars'],attack['destructionPercentage'],datetime.now(),attack['duration']
                            ))





class player:

    def __init__(self,tag,session):
        self.session = session
        self.data = session.getData(f"players/{tag}")
        self.playerTag = self.data['tag']
        self.clanTag = self.data['clan']['tag']
        self.name = self.data['name']

        self.savePlayer()
        self.snapshot = self.getNewSnapshot(getData = False)

    def getNewSnapshot(self,getData = True):
        if getData:
            self.data = self.session.getData(f"players/{self.playerTag}")
        snap = playerSnapshot(self)
        snap.saveSnapshot(self.session.db)
        return snap

    def activityCheck(self):
        self.data = self.session.getData(f"players/{self.playerTag}")

        sql = """
        SELECT builderBaseTrophies, donations, donationsRecieved FROM PlayerSnapshot WHERE playerTag = ? ORDER BY time DESC LIMIT 1;
        """
        result = self.session.db.execute(sql,(self.playerTag,))
        if result:
            data = result[0]

            if (data[0] != self.data['builderBaseTrophies'] or
                    data[1] < self.data['donations'] or
                    data[2] < self.data['donationsReceived']):

                sql = "INSERT IGNORE INTO ActivitySnapshot (playerTag, time) VALUES (?, ?)"
                self.session.db.execute(sql, (self.playerTag, datetime.now()))

    def savePlayer(self):

        if self.clanTag:
            check_clan_sql = "SELECT 1 FROM Clan WHERE tag = ?"
            if not self.session.db.execute(check_clan_sql, (self.clanTag,)):
                self.clanTag = None  # Unlink from unknown clan


        # Check if player is already saved
        sql = "SELECT playerTag FROM Player WHERE playerTag = ?;"
        names = self.session.db.execute(sql, (self.playerTag,))

        if not names:
            sql = "INSERT IGNORE INTO Player(playerTag, clanTag, name) Values(?, ?, ?)"
            self.session.db.execute(sql, (self.playerTag, self.clanTag, self.name))
        else:
            # Handle returning players or name changes
            sql = "UPDATE Player SET clanTag = ?, name = ? WHERE playerTag = ?"
            self.session.db.execute(sql, (self.clanTag, self.name, self.playerTag))

class playerSnapshot:

    def __init__(self,player):
        self.clanTag = player.clanTag
        self.playerTag = player.playerTag


        self.townHallLevel = player.data.get('townHallLevel', 1)
        self.exLevel = player.data.get('expLevel', 1)
        self.warStars = player.data.get('warStars', 0)


        self.builderHallLevel = player.data.get('builderHallLevel', 0)
        self.builderBaseTrophies = player.data.get('builderBaseTrophies', 0)

        self.role = player.data.get('role', 'member')
        self.warPreference = player.data.get('warPreference', 'out')
        self.donations = player.data.get('donations', 0)
        self.donationsReceived = player.data.get('donationsReceived', 0)
        self.clanCapitalContributions = player.data.get('clanCapitalContributions', 0)


        if 'league' in player.data and player.data['league']:
            self.league = player.data['league']['name']
        else:
            self.league = 'Unranked'

        self.time = datetime.now()
    def saveSnapshot(self,db):
        sql = """
        INSERT IGNORE INTO PlayerSnapshot 
        (playerTag,time,clanTag,townHallLevel,exLevel,warStars,builderHallLevel,builderBaseTrophies,role,warPreference,donations,donationsRecieved,clanCapitalContributions,league)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?);

        """

        db.execute(sql,(self.playerTag,self.time,self.clanTag,self.townHallLevel,self.exLevel,self.warStars,self.builderHallLevel,self.builderBaseTrophies,self.role,self.warPreference,self.donations,self.donationsReceived,self.clanCapitalContributions,self.league))



