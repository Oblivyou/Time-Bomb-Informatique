import os

# import sys
import asyncio
from time import sleep
from random import randint, shuffle, choice
from threading import Thread
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    UdpTransportTarget,
    walk_cmd,
)


class Player:
    def __init__(self):
        self.n = 0
        self.role = "?"
        self.cards = []
        self.expectation = 0
        self.ip = "?"

    def __str__(self):
        return f"{self.n} | {self.role} | {self.cards}"


# os.system('cls')


# game variables
players = []
roles = []
deck = []
# game tracking
win = False
defuse = 0
round_cnt = 0
state = "?"
p1 = "?"
# players_count = 0
players_ready = 0
pulls = 0
ready = False
pull_res = {"type": "?", "from": Player()}
error = False


def loop_scan():
    while True:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(scan())
        # loop.close()
        sleep(6)


async def scan():
    """
    scans switches in expectation and return if all is as expected
    directly prompts to balance cables if not as expected

    params: expectation list of Player class

    return:
        True if all as expected else False
    """
    # BASE_IP = "192.168.1."
    # start_ip = 2
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    target_ips = []
    global players
    expectation = players
    global error
    # extract ips from player list
    for p in expectation:
        # print(p.ip)
        target_ips.append(p.ip)
    print("scanning-->")

    PORT = 161
    COMMUNITY_STRING = "public"
    TARGET_OID = "1.3.6.1.2.1.2.2.1.8"
    result = []
    # run trough all switches
    for target_ip in target_ips:
        # make current ip
        # target_ip = BASE_IP + str(i)
        # print(target_ip)
        transport_target = await UdpTransportTarget.create((target_ip, PORT))
        iterator = walk_cmd(
            SnmpEngine(),
            CommunityData(COMMUNITY_STRING),
            transport_target,
            ContextData(),
            ObjectType(ObjectIdentity(TARGET_OID)),
            lexicographicMode=False,
        )
        count = 0
        async for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            # managing errors
            if errorIndication or errorStatus:
                print(f"caught Error: {errorIndication or errorStatus}")
                break
            # unpacking variable bindings
            for varBind in varBinds:
                oid, value = varBind
                port_index = oid.asTuple()[-1]
                # counting active ports
                if port_index <= 0:
                    continue
                if port_index > 0 and port_index < 8:
                    if value == 1:
                        count += 1
                if port_index == 8:
                    if value == 1:
                        count += 1
                # end of loop action
        result.append(count)
        # print(f' active count on {i-1} : {count}')
    # print(result)
    # print(expectation)
    # test expectations agains results
    as_expected = True
    i = 0
    for p in expectation:
        res = result[i]
        exp = p.expectation
        if res != exp:
            as_expected = False
            error = True
            if res < exp:
                print(f"player {p.n} plug cables until {exp}")
            elif res > exp:
                print(f"player {p.n} unplug cables until {exp}")

        i += 1
    if as_expected:
        error = False
        print("as expected")
        if state == "call_player":
            print("player ", p1.n, " proceed")

    # return as_expected


def trap_listener():
    """
    listens to incoming traps and triggers game actions
    """

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    snmp_engine = engine.SnmpEngine()

    # function called when trap is detected
    def cbFun(
        snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx
    ):
        global state
        global error
        print("[TRAP RECEIVED]")
        # origin of trap switch ip
        exec_context = snmpEngine.observer.get_execution_context(
            "rfc3412.receiveMessage:request"
        )
        # number of switch defined by last ip number start on 2 -> 7 (6 total)
        ip = int(exec_context["transportAddress"][0].split(".")[-1]) - 1

        print("switch", ip)
        # port number
        # print('port : ',varBinds[2][1])

        # if is plugged
        if varBinds[4][1] == 1:
            # use scan
            print(state)
            # is_ok = loop.run_until_complete(scan(players))
            if not error:
                print("re-plugged - all ok")
            else:
                print("re-plugged - not ok")
        # if is unplugged
        elif varBinds[4][1] == 2:
            # use pick
            if state == "call_player" and p1.n != ip and not error:
                global pull_res
                pull_res = pick_card(p1, players[ip - 1])

                state = "pulled"
            else:
                error = True
                # loop.run_until_complete(scan(players))
                print("unexpected unplug")
        # print("-" * 50 + "\n")

    config.add_transport(
        snmp_engine,
        udp.DOMAIN_NAME + (1,),
        udp.UdpTransport().open_server_mode(("192.168.1.1", 1001)),
    )
    config.add_v1_system(snmp_engine, "my-area", "public")
    ntfrcv.NotificationReceiver(snmp_engine, cbFun)
    try:
        snmp_engine.transport_dispatcher.job_started(1)
        snmp_engine.transport_dispatcher.run_dispatcher()
    except KeyboardInterrupt:
        print("\nStopping")


# g = Game()


def setup(n_p):
    """
    sets up the game according to the number of players

    params:
        n_p : number of players
    """
    global defuse
    defuse = 0
    global round_cnt
    round_cnt = 0
    global win
    win = False
    global pull_reveal
    pull_reveal = {"type": "?", "from": Player()}
    players.clear()
    for i in range(1, n_p + 1):
        p = Player()
        p.n = i
        p.ip = "192.168.1." + str(p.n + 1)
        players.append(p)
    deck.clear()
    for i in range(n_p * 5):
        if len(deck) == 0:
            deck.append("b")  # b bomb
        elif len(deck) < n_p + 1:
            deck.append("d")  # d defuse
        else:
            deck.append("s")  # s safe
    roles.clear()
    sh = 3
    mo = 2
    if n_p == 6:
        sh = 4
    elif n_p > 6:
        sh = 4
        mo = 3
    for i in range(sh):
        roles.append("SH")
    for i in range(mo):
        roles.append("MO")


def give_roles():
    """
    gives each player a role
    """
    shuffle(roles)
    for p in players:
        pick = roles.pop()
        p.role = pick


def draw_cards():
    """
    draws each player up to 5 cards or until deck empty
    """
    # take cards from players
    global round_cnt
    round_cnt += 1
    for p in players:
        if len(p.cards) > 0:
            deck.extend(p.cards)
            p.cards.clear()
            p.expectation = 0
    # redistribute cards
    shuffle(deck)
    while len(deck) >= len(players):
        for p in players:
            if len(p.cards) < 5:
                p.cards.append(deck.pop())
                p.expectation += 1


def pick_card(who, pulled, wich="r"):
    """
    picks a card from a player

    params:
        who : player pulling
        pulled : player being pulled from
        wich : the card id being pulled by default random
    return:
        result : contains "team" (team who pulled the card) "pull" (the type of card pulled)
    """
    global defuse
    team = who.role
    player = who.n
    pulled.expectation -= 1
    if wich == "r":
        pull = pulled.cards.pop(randint(0, len(pulled.cards) - 1))
    else:
        pull = pulled.cards.pop(wich)
    if pull == "d":
        defuse += 1
    print(f"player {player} from {team} pulled {pull} from player {pulled.n}")
    return {"from": pulled, "type": pull}


# gameplay test

os.system("cls")


def game():
    global state
    global ready
    global win
    global defuse
    global round_cnt
    global p1
    # global players_count
    global players_ready
    global pulls

    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # state: player readinness check
    # condition: all players ready (full server)
    state = "player_check"  # only join available on screen
    # while len(players) < 6 or not ready:
    #     if len(players) >= 4 :
    #         state = "player_ready" # ready available
    #     if len(players) == players_ready:
    #         ready = True #exits loop
    # setup(len(players))
    setup(4)
    give_roles()
    state = "give_roles"  # show role to player
    # sleep(5000) # give time to memorize roles

    # pull until pulls = n of players or win = true, round count is actual-1 at this point
    while not win and round_cnt < 4:
        draw_cards()  # also round_count +1
        print("------------------round  : ", round_cnt)
        # try to start game
        state = "game_start"
        while state == "game_start":
            print("game starting ...")

            # if cabling is ok
            # is_ok = loop.run_until_complete(scan(players))
            if not error:
                # game starts
                state = "started"  # display nothing
        # for p in players:
        #     print(p)
        pulls = 0
        p1 = "?"
        # pull until pulls = n of players or win = true
        while not win and pulls < len(players):
            # player selection and call
            # 1st player each round random
            if p1 == "?":
                p1 = choice(players)
            state = "call_player"  # ask player to remove cable
            print("calling", p1.n)
            while state == "call_player":
                sleep(2)
                # asyncio.sleep(1)
                # sleep(200)
                # sleep(500) # unplug cause call_player state to end, by setting state = pulled

            pulls += 1
            # make info available once then wipe
            state = "reveal"  # show card pulled to all players
            print(pull_res["type"], "<------", pull_res["from"])
            if pull_res["type"] == "b":
                print("----------------Team Moriarty wins----------------")
                win = True
                state = "win"
            elif pull_res["type"] == "d" and defuse == len(players):
                print("----------------Team Sherlock wins----------------")
                win = True
                state = "win"
            if win:
                break
            else:
                p1 = pull_res["from"]
    # if game not won at end of turn 4 MO wins
    if not win:
        win = True
        state = "win"
        print("----------------Team Moriarty wins----------------")


if __name__ == "__main__":
    Thread(target=trap_listener, daemon=True).start()
    Thread(target=loop_scan, daemon=True).start()
    game()
