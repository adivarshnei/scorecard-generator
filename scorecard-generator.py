import json
import os
import re
import time

import bs4
import feedparser
import pandas as pd
import requests


def get_scorecard(
    feed: "feedparser.util.FeedParserDict" = None,
    game: int = -1,
    code: int = -1,
) -> None:
    if code == -1:
        json_url: str = f"{feed.entries[game].id[:-5]}.json"

        html_url = (
            f"{requests.get(f'{json_url[:-5]}.html').url[:-19]}/full-scorecard"
        )
    else:
        json_url = (
            f"https://www.espncricinfo.com/matches/engine/match/{code}.json"
        )

        html_url = f"{requests.get(f'https://www.espncricinfo.com/matches/engine/match/{code}.html').url}"
        if not html_url.endswith("full-scorecard"):
            print("Nope")

    json_dict = json.loads(requests.get(json_url).text)

    match_description = json_dict["description"]
    umpires = [
        x["card_long"]
        for x in json_dict["official"]
        if x["player_type_name"] == "umpire"
    ]

    player_dict = {}

    for x in json_dict["team"]:
        for y in x["player"]:
            player_dict[y["known_as"]] = [
                y["card_long"],
                y["captain"],
                y["keeper"],
            ]

    page = requests.get(html_url)
    soup = bs4.BeautifulSoup(markup=page.content, features="lxml")

    table_body = soup.find_all("tbody")

    found = re.findall(r"[^/]*(?:\/full-scorecard)", html_url)[0][
        : -(len("full-scorecard") + 1)
    ].split("-")

    t1 = []
    t2 = []
    splitloc = len(found)

    for i in range(len(found)):
        if found[i] != "vs":
            t1.append(found[i])
        else:
            splitloc = i
            break

    for i in range(splitloc + 1, len(found)):
        if not found[i][0].isdigit():
            t2.append(found[i])
        else:
            break

    t1 = " ".join(t1).title()
    t2 = " ".join(t2).title()

    inns_order = re.findall(
        r'<span class="ds-text-title-xs ds-font-bold ds-capitalize">\s*([A-Za-z0-9 ]*)\s*</span>',
        string=soup.prettify(),
    )

    teams = [json_dict["match"]["team1_name"], json_dict["match"]["team2_name"]]

    bats = pd.DataFrame(columns=["Name", " ", "R", "B", "4", "6", "SR", "Inns"])
    totals = []

    for i, table in enumerate(table_body[0::2]):
        rows = table.find_all("tr")

        for row in rows:

            cols = row.find_all("td")
            cols = [x.text.strip() for x in cols]

            if (
                cols[0] == "Extras"
                or cols[0] == ""
                or cols[0][:15] == "Fall of wickets"
            ):
                continue
            elif len(cols) > 7:
                name = cols[0].replace("\xa0", " ").replace("(c)", "*")

                for key, value in player_dict.items():
                    name = name.replace(key, value[0])

                if " " in name:
                    f, l = name.split(" ", 1)

                    if f.isupper():
                        f = ".".join(f[i : i + 1] for i in range(len(f))) + "."

                    name = " ".join([f, l])

                new = [
                    [
                        name,
                        cols[1],
                        str(cols[2]),
                        str(cols[3]),
                        str(cols[5]),
                        str(cols[6]),
                        str(cols[7]),
                        str(i + 1),
                    ]
                ]

                bats = pd.concat(
                    objs=[bats, pd.DataFrame(new, columns=bats.columns)],
                    ignore_index=True,
                )

            elif cols[0][:10] == "Yet to bat":
                for name in cols[0][12:].replace("\xa0", " ").split(", "):
                    for key, value in player_dict.items():
                        name = name.replace(key, value[0])

                    f, l = name.split(" ", 1)

                    if f.isupper():
                        f = ".".join(f[i : i + 1] for i in range(len(f))) + "."

                    name = " ".join([f, l])

                    new = [
                        [
                            name.replace("(c)", "*"),
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            str(i + 1),
                        ]
                    ]
                    bats = pd.concat(
                        objs=[bats, pd.DataFrame(new, columns=bats.columns)],
                        ignore_index=True,
                    )

            elif cols[0][:11] == "Did not bat":
                for name in cols[0][13:].replace("\xa0", " ").split(", "):

                    name = name.replace("\xa0", " ").replace("(c)", "*")
                    for key, value in player_dict.items():
                        name = name.replace(key, value[0])

                    if " " in name:
                        f, l = name.split(" ", 1)

                        if f.isupper():
                            f = (
                                ".".join(f[i : i + 1] for i in range(len(f)))
                                + "."
                            )

                        name = " ".join([f, l])

                    new = [[name, "DNB", "", "", "", "", "", str(i + 1)]]
                    bats = pd.concat(
                        objs=[bats, pd.DataFrame(new, columns=bats.columns)],
                        ignore_index=True,
                    )
            elif cols[0] == "TOTAL":
                totals.append([x.replace("\xa0", " ") for x in cols])

    bowls = pd.DataFrame(
        columns=[
            "Name",
            "O",
            "M",
            "R",
            "W",
            "E",
            "0",
            "4",
            "6",
            "Wd",
            "Nb",
            "Inns",
        ]
    )

    for i, table in enumerate(table_body[1::2]):
        rows = table.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            cols = [x.text.strip() for x in cols]

            if cols[0][0].isdigit():
                continue
            elif len(cols) == len(bowls.columns) - 1:
                name = cols[0]
                for key, value in player_dict.items():
                    name = name.replace(key, value[0])

                if " " in name:
                    f, l = name.split(" ", 1)

                    if f.isupper():
                        f = ".".join(f[i : i + 1] for i in range(len(f))) + "."

                    name = " ".join([f, l])

                bowls = pd.concat(
                    objs=[
                        bowls,
                        pd.DataFrame(
                            [[name] + cols[1:] + [str(i + 1)]],
                            columns=bowls.columns,
                        ),
                    ],
                    ignore_index=True,
                )

    bats.reset_index()

    bat_lens = [max([len(str(y)) for y in bats[x]]) for x in bats.columns]
    bowl_lens = [max([len(str(y)) for y in bowls[x]]) for x in bowls.columns]

    for total in totals:
        for i in range(len(total)):
            bat_lens[i] = (
                len(total[i]) if len(total[i]) > bat_lens[i] else bat_lens[i]
            )

    time.sleep(0.02)
    print()
    time.sleep(0.02)
    print("*" * 80)

    time.sleep(0.02)
    print(f"{match_description}\n")
    time.sleep(0.02)
    print(f"Umpires: {', '.join(umpires)}\n")
    time.sleep(0.02)
    print(f"URL: {html_url}\n")

    for i in bats.Inns.unique():
        time.sleep(0.02)
        print("-" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1)))
        time.sleep(0.02)
        print(f"Inning {i} : {inns_order[int(i)-1]}")
        time.sleep(0.02)
        print("-" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1)))

        time.sleep(0.02)
        print(
            "".join(
                [
                    "{str:{width}}".format(str=p, width=bat_lens[j] + 3)
                    for j, p in enumerate(
                        bats.loc[:, bats.columns != "Inns"].columns
                    )
                ]
            )
        )

        for _, x in bats[bats.Inns == i].iterrows():
            time.sleep(0.02)

            for j in range(len(bats.loc[:, bats.columns != "Inns"].columns)):
                print(
                    "{str:{width}}".format(
                        str=str(x[j]), width=bat_lens[j] + 3
                    ),
                    end="",
                )

            print()

        time.sleep(0.02)
        print("-" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1)))

        time.sleep(0.02)
        print(
            "".join(
                [
                    "{str:{width}}".format(
                        str=str(totals[int(i) - 1][j]), width=bat_lens[j] + 3
                    )
                    for j in range(len(totals[int(i) - 1]))
                ]
            ),
        )

        time.sleep(0.02)
        print("-" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1)))

        time.sleep(0.02)
        print("\n\n")

        time.sleep(0.02)
        print("-" * (sum(bowl_lens[:-1]) + 3 * (len(bowl_lens[:-1]) - 1) + 1))
        time.sleep(0.02)
        print(
            f"Inning {i} : {[x for x in teams if x != inns_order[int(i)-1]][0]}"
        )
        time.sleep(0.02)
        print("-" * (sum(bowl_lens[:-1]) + 3 * (len(bowl_lens[:-1]) - 1) + 1))

        time.sleep(0.02)
        print(
            "".join(
                [
                    "{str:{width}}".format(str=p, width=bowl_lens[j] + 3)
                    for j, p in enumerate(
                        bowls.loc[:, bowls.columns != "Inns"].columns
                    )
                ]
            )
        )

        for _, x in bowls[bowls.Inns == i].iterrows():
            time.sleep(0.02)

            for j in range(len(bowls.loc[:, bowls.columns != "Inns"].columns)):
                print(
                    "{str:{width}}".format(
                        str=str(x[j]), width=bowl_lens[j] + 3
                    ),
                    end="",
                )

            print()

        time.sleep(0.02)
        print("-" * (sum(bowl_lens[:-1]) + 3 * (len(bowl_lens[:-1]) - 1) + 1))

        time.sleep(0.02)
        print("\n")

    print()
    print("*" * 80)


def main() -> None:
    while True:
        feed: feedparser.util.FeedParserDict = feedparser.parse(
            "https://www.espncricinfo.com/rss/livescores.xml"
        )

        last = 0

        time.sleep(0.02)
        print("Current Matches: ")

        for i, x in enumerate(feed.entries):
            time.sleep(0.02)
            print(f"{i + 1}: {x.title}")
            last = i

        last += 1

        time.sleep(0.02)
        print("\nOther options: ")

        time.sleep(0.02)
        print(f"{last + 1}: Custom Code")
        time.sleep(0.02)
        print(f"{last + 2}: Exit")

        time.sleep(0.02)
        game: int = int(input("Enter game: "))

        os.system("cls")

        if game == last + 1:
            time.sleep(0.02)
            code = int(input("Enter match code: "))

            # os.system("cls")

            while True:
                os.system("cls")
                get_scorecard(code=code)
                time.sleep(5)
        elif game == last + 2:
            break
        else:
            # os.system("cls")

            while True:
                os.system("cls")
                get_scorecard(feed=feed, game=game - 1)
                time.sleep(5)


if __name__ == "__main__":
    main()
