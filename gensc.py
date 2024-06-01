#!/usr/bin/env python3

import json
import os
import re
import sys
import time
import warnings
import typing

import bs4
import feedparser
import pandas as pd
import requests

SLEEPTIME: float = 0.05


def clear_line():
    # time.sleep(SLEEPTIME)
    # cols, _ = os.get_terminal_size(0)
    # print(" " * cols, end="\r")
    pass


def get_scorecard(
    feed: "feedparser.util.FeedParserDict" = None,  # type: ignore
    game: int = -1,
    code: int = -1,
) -> None:
    json_url: str
    html_url: str

    if code == -1:
        json_url = f"{feed.entries[game].id[:-5]}.json"

        # print(f"JSON link: {json_url}")

        html_url = (
            f"{requests.get(f'{json_url[:-5]}.html').url[:-19]}/full-scorecard"
        )
    else:
        json_url = (
            f"https://www.espncricinfo.com/matches/engine/match/{code}.json"
        )

        html_url = f"{requests.get(f'https://www.espncricinfo.com/matches/engine/match/{code}.html').url}"
        # if not html_url.endswith("full-scorecard"):
        #     print("Nope")

    json_dict: dict[str, typing.Any] = json.loads(requests.get(json_url).text)

    match_description: str = json_dict["description"]
    match_description = match_description.replace(
        match_description[
            match_description.find(" at ")
            + 4 : match_description.find(",", match_description.find(" at "))
        ],
        json_dict["match"]["ground_name"],
    )

    umpires: list[str] = [
        x["card_long"]
        for x in json_dict["official"]
        if x["player_type_name"] == "umpire"
    ]

    player_dict: dict[str, list] = {}

    for x in json_dict["team"]:
        for y in x["player"]:
            player_dict[y["known_as"]] = [
                y["card_long"],
                y["captain"],
                y["keeper"],
            ]

    if html_url.endswith("live-cricket-score"):
        html_url = html_url[: -len("live_cricket_score")] + "full-scorecard"

    page: requests.Response = requests.get(html_url)
    soup: bs4.BeautifulSoup = bs4.BeautifulSoup(
        markup=page.content, features="lxml"
    )

    table_body: bs4.element.ResultSet[bs4.element.Tag] = soup.find_all("tbody")

    found: list[str] = re.findall(r"[^/]*(?:\/full-scorecard)", html_url)[0][
        : -(len("full-scorecard") + 1)
    ].split("-")

    t1_l: list[str] = []
    t2_l: list[str] = []
    splitloc: int = len(found)

    for i in range(len(found)):
        if found[i] != "vs":
            t1_l.append(found[i])
        else:
            splitloc = i
            break

    for i in range(splitloc + 1, len(found)):
        if not found[i][0].isdigit():
            t2_l.append(found[i])
        else:
            break

    # t1: str = " ".join(t1_l).title()
    # t2: str = " ".join(t2_l).title()

    inns_order: list[str] = re.findall(
        r'<span class="ds-text-title-xs ds-font-bold'
        r' ds-capitalize">\s*([A-Za-z0-9'
        r" ]*)\s*</span>",
        string=soup.prettify(),
    )

    if len(inns_order) == 0:
        inns_order = [str(x["batting_team_id"]) for x in json_dict["innings"]]

        inns_order[:] = [
            (
                x
                if x != json_dict["match"]["team1_id"]
                else json_dict["match"]["team1_name"]
            )
            for x in inns_order
        ]

        inns_order[:] = [
            (
                x
                if x != json_dict["match"]["team2_id"]
                else json_dict["match"]["team2_name"]
            )
            for x in inns_order
        ]

    teams: list[str] = [
        json_dict["match"]["team1_name"],
        json_dict["match"]["team2_name"],
    ]

    bats: pd.DataFrame = pd.DataFrame(
        columns=["Name", " ", " ", "R", "B", "4", "6", "SR", "Inns"]
    )
    totals: list[list[str]] = []

    for i, table in enumerate(table_body[0::2]):
        rows: bs4.element.ResultSet[bs4.element.Tag] = table.find_all("tr")

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
                name: str = (
                    cols[0]
                    .replace("\xa0", " ")
                    .replace("(c)", "*")
                    .replace("†", "+")
                )

                if " b " in cols[1]:
                    status_first = cols[1][: cols[1].index(" b ")].replace(
                        "†", "+"
                    )
                    status_second = cols[1][cols[1].index(" b ") + 1 :].replace(
                        "†", "+"
                    )
                elif cols[1][:2] == "b ":
                    status_first = ""
                    status_second = cols[1].replace("†", "+")
                elif cols[1][:7] == "run out":
                    status_first = "run out"
                    status_second = cols[1][8:] if len(cols) > 7 else ""
                else:
                    status_first = cols[1].replace("†", "+")
                    status_second = ""

                for key, value in player_dict.items():
                    name = name.replace(key, value[0])

                if " " in name:
                    f: str
                    l: str
                    f, l = name.split(" ", 1)

                    if f.isupper():
                        f = ".".join(f[i : i + 1] for i in range(len(f))) + "."

                    name = " ".join([f, l])

                new: list[list[str]] = [
                    [
                        name,
                        status_first,
                        status_second,
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

                    if " " in name:
                        f, l = name.split(" ", 1)

                        if f.isupper():
                            f = (
                                ".".join(f[i : i + 1] for i in range(len(f)))
                                + "."
                            )

                        name = " ".join([f, l])

                    new = [
                        [
                            name.replace("(c)", "*").replace("†", "+"),
                            "",
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
                    name = (
                        name.replace("\xa0", " ")
                        .replace("(c)", "*")
                        .replace("†", "+")
                    )

                    for key, value in player_dict.items():
                        name = name.replace(key, value[0])

                    if " " in name:
                        f, l = name.split(" ", 1)

                        if f.isupper():
                            f = (
                                ".".join(f[i : i + 1] for i in range(len(f)))
                                + "."
                            )
                            # print(f)

                        name = " ".join([f, l])

                    new = [[name, "DNB", "", "", "", "", "", "", str(i + 1)]]
                    bats = pd.concat(
                        objs=[bats, pd.DataFrame(new, columns=bats.columns)],
                        ignore_index=True,
                    )
            elif cols[0] == "TOTAL":
                totals.append([x.replace("\xa0", " ") for x in cols])

    for total in totals:
        total.insert(2, "")

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

            # print(cols)

            # print(len(cols), len(bowls.columns))

            if len(cols[0]) == 0:
                continue
            elif cols[0][0].isdigit():
                continue
            elif len(cols) >= len(bowls.columns) - 1:
                cols = cols[: len(bowls.columns) - 1]
                name = cols[0]
                for key, value in player_dict.items():
                    name = name.replace(key, value[0])

                if " " in name:
                    f, l = name.split(" ", 1)

                    if f.isupper():
                        f = ".".join(f[i : i + 1] for i in range(len(f))) + "."

                    name = " ".join([f, l])

                bowls: pd.DataFrame = pd.concat(
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

    if code == -1:
        os.system("printf '\\33c\\e[3J'")
        # os.system("printf '\\e[H'")
    clear_line()
    print()
    clear_line()
    # print("═" * 80)
    print(f"{match_description}\n")
    clear_line()
    print(f"Umpires: {', '.join(umpires)}\n")
    clear_line()
    print(f"URL: {html_url}\n")
    clear_line()
    print(f"{json_dict['live']['status']}\n")
    clear_line()

    try:
        bat_lens: list[int] = [
            max([len(str(y)) for y in bats[x]]) for x in bats.columns
        ]
        # print(bowls)
        bowl_lens: list[int] = [
            max([len(str(y)) for y in bowls[x]]) for x in bowls.columns
        ]

        bat_lens[1] = max([len(x) for x in bats.iloc[:, 1]])
        bat_lens[2] = max([len(x) for x in bats.iloc[:, 2]])

        for i in bats.Inns.unique():
            # print("━" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1) + 1))
            print(f"Inning {i} : {inns_order[int(i)-1]}")
            clear_line()
            # print("━" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1) + 1))
            print(
                "".join(
                    [
                        "{str:{width}}".format(str=p, width=bat_lens[j] + 3)
                        for j, p in enumerate(
                            bats.loc[:, bats.columns != "Inns"].columns  # type: ignore
                        )
                    ]
                )
            )
            clear_line()

            for _, x in bats[bats.Inns == i].iterrows():
                for j in range(len(bats.loc[:, bats.columns != "Inns"].columns)):  # type: ignore
                    with warnings.catch_warnings():
                        warnings.simplefilter(
                            action="ignore", category=FutureWarning
                        )
                        print(
                            "{str:{width}}".format(
                                str=str(x[j]), width=bat_lens[j] + 3
                            ),
                            end="",
                        )

                print()
                clear_line()

            # print("━" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1) + 1))
            widths: list[int] = [
                bat_lens[0] + 3,
                bat_lens[1] + 3 + bat_lens[2] + 3,
                0,
                0,
                0,
            ]
            print(
                "".join(
                    [
                        "{str:{width}}".format(
                            str=str(totals[int(i) - 1][j]),
                            width=widths[j],
                        )
                        for j in range(len(totals[int(i) - 1]))
                    ]
                ),
            )
            clear_line()
            # print("━" * (sum(bat_lens[:-1]) + 3 * (len(bat_lens[:-1]) - 1) + 1))
            print()
            clear_line()
            # print(
            #     "━" * (sum(bowl_lens[:-1]) + 3 * (len(bowl_lens[:-1]) - 1) + 1)
            # )
            print(
                f"Inning {i} : {[x for x in teams if x != inns_order[int(i)-1]][0]}"
            )
            clear_line()
            # print(
            #     "━" * (sum(bowl_lens[:-1]) + 3 * (len(bowl_lens[:-1]) - 1) + 1)
            # )
            print(
                "".join(
                    [
                        "{str:{width}}".format(str=p, width=bowl_lens[j] + 3)
                        for j, p in enumerate(
                            bowls.loc[:, bowls.columns != "Inns"].columns  # type: ignore
                        )
                    ]
                )
            )
            clear_line()

            for _, x in bowls[bowls.Inns == i].iterrows():
                for j in range(len(bowls.loc[:, bowls.columns != "Inns"].columns)):  # type: ignore
                    with warnings.catch_warnings():
                        warnings.simplefilter(
                            action="ignore", category=FutureWarning
                        )
                        print(
                            "{str:{width}}".format(
                                str=str(x[j]), width=bowl_lens[j] + 3
                            ),
                            end="",
                        )

                print()
                clear_line()

            # print(
            #     "━" * (sum(bowl_lens[:-1]) + 3 * (len(bowl_lens[:-1]) - 1) + 1)
            # )
            print("\n")
            clear_line()
    except:
        print()
        clear_line()
    print()
    clear_line()
    # print("═" * 80)


def main() -> None:
    if len(sys.argv) > 1:
        get_scorecard(code=int(sys.argv[1]))
    else:
        print("1. Get Current Matches")
        print("2. Custom Code")
        print("3. Exit")

        choice: int = int(input("Enter option: "))

        if choice == 1:
            while True:
                feed: feedparser.util.FeedParserDict = feedparser.parse(
                    "https://www.espncricinfo.com/rss/livescores.xml"
                )

                last = 0

                print("Current Matches: ")

                for i, x in enumerate(feed.entries):
                    print(f"{i + 1}: {x.title}")
                    last: int = i

                last += 1

                game: int = int(input("Enter game: "))
                os.system("printf '\\33c\\e[3J'")

                while True:
                    get_scorecard(feed=feed, game=game - 1)

                    time.sleep(5)

        elif choice == 2:
            code = int(input("Enter match code: "))

            while True:
                get_scorecard(code=code)
                time.sleep(15)
        elif choice == 3:
            pass


if __name__ == "__main__":
    main()
