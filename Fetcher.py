from datetime import datetime
from os import environ
import urllib.parse
import dotenv
import requests
from DBManager import DBManager


class FetchSession:

    def __init__(self):
        self.URL = "https://api.clashofclans.com/v1/"
        dotenv.load_dotenv()
        self.TOKEN = environ.get("TOKEN")
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.TOKEN}"
        }

        self.db = DBManager("192.168.1.18","Home_User", "Tamer@2006","clash_db")


    def getData(self,endpoint):
        data = None
        try:

            encoded_tag = urllib.parse.quote(endpoint)
            URL = f"https://api.clashofclans.com/v1/{encoded_tag}"
            response = requests.get(URL, headers=self.headers)

            # 5. Check for successful response
            if response.status_code == 200:
                data  = response.json()
                print("Got Data")
            else:
                print(f"Error fetching data. Status code: {response.status_code}")
                print(response.text)  # Shows the error message from the API

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
        INSERT INTO League (name, iconURL) VALUES (?,?)
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

    def saveClanData(self):
        sql = """
        SELECT tag FROM Clan WHERE tag = ?;
        """
        clans = self.session.db.execute(sql,(self.clanTag,))
        if not clans:
            sql = """
            INSERT INTO Clan(tag,name,level) Values(?,?,?)
            """
            self.session.db.execute(sql, (self.clanTag,self.name,self.level))





class clanWar:

    def __init__(self,session,tag):
        self.session = session
        self.data = session.getData(f"clans/{tag}/currentwar")
        self.clanTag1 = tag
        self.clanTag2 = self.data['opponent']['tag']
        self.state = self.data['state']
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
        sql = """
        SELECT warID FROM ClanWar WHERE (clanTag1 = ? AND clanTag2 = ?) AND state IN ('preparation', 'inWar');
        """
        wars = self.session.db.execute(sql,(self.clanTag1,self.clanTag2,))
        if not wars:
            sql = """
            INSERT INTO ClanWar(clanTag1,clanTag2,state,teamSize,startTime,endTime,warType,leagueGroupId,league) Values(?,?,?,?,?,?,?,?,?)
            """

            self.session.db.execute(sql, (self.clanTag1, self.clanTag2, self.state, self.teamSize, self.teamSize,
                                          self.endTime, self.warType, self.leagueGroupID, self.league))
            id = self.session.db.execute("SELECT LAST_INSERT_ID();")
            self.id = id[0][0]

        else:
            self.id = wars[0][0]
            update_sql = "UPDATE ClanWar SET state = ? WHERE warID = ?"
            self.session.db.execute(update_sql, (self.state, self.id))



class warResults:

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
                            INSERT INTO WarResults (warID, clanTag, totalDestruction, totalStars, result)
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
        INSERT INTO WarPlayer (warID,playerTag,mapPosition,townHallLevel,name,clanTag) VALUES (?,?,?,?,?,?)
        """
        session.db.execute(sql,(war.id, self.playerTag,self.mapPosition,self.townHallLevel,self.name,self.clanTag,))


class attack:

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
                                INSERT INTO Attack (warID, attackerTag, defenderTag, stars, destruction, startTime, duration)
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
                            INSERT INTO Attack (warID, attackerTag, defenderTag, stars, destruction, startTime, duration)
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
        self.snapshot = self.getNewSnapshot()
        self.savePlayer()

    def getNewSnapshot(self):
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

                sql = "INSERT INTO ActivitySnapshot (playerTag, time) VALUES (?, ?)"
                self.session.db.execute(sql, (self.playerTag, datetime.now()))

    def savePlayer(self):
        #check is player is already saved
        sql = """
        SELECT playerTag FROM Player WHERE playerTag = ?;
        """
        names = self.session.db.execute(sql,(self.playerTag,))
        if not names:
            sql = """
            INSERT INTO Player(playerTag,clanTag,name) Values(?,?,?)
            """
            self.session.db.execute(sql, (self.playerTag,self.clanTag,self.name))



class playerSnapshot:

    def __init__(self,player):
        self.clanTag =player.clanTag
        self.playerTag =player.playerTag
        self.townHallLevel = player.data['townHallLevel']
        self.exLevel = player.data['expLevel']
        self.warStars = player.data['warStars']
        self.builderHallLevel = player.data['builderHallLevel']
        self.builderBaseTrophies = player.data['builderBaseTrophies']
        self.role =player.data['role']
        self.warPreference = player.data['warPreference']
        self.donations = player.data['donations']
        self.donationsReceived = player.data['donationsReceived']
        self.league = player.data['leagueTier']['name']
        self.clanCapitalContributions = player.data['clanCapitalContributions']
        self.time = datetime.now()

    def saveSnapshot(self,db):
        sql = """
        INSERT INTO PlayerSnapshot 
        (playerTag,time,clanTag,townHallLevel,exLevel,warStars,builderHallLevel,builderBaseTrophies,role,warPreference,donations,donationsRecieved,clanCapitalContributions,league)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?);

        """

        db.execute(sql,(self.playerTag,self.time,self.clanTag,self.townHallLevel,self.exLevel,self.warStars,self.builderHallLevel,self.builderBaseTrophies,self.role,self.warPreference,self.donations,self.donationsReceived,self.clanCapitalContributions,self.league))



