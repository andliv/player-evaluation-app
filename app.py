import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Player Evaluation Dashboard",
    layout="wide"
)

st.title("📊 Player Evaluation Dashboard")

tab_overview, tab_profile, tab_compare = st.tabs(
    ["📋 Player summary", "🧑‍💼 Player profile", "⚖️ Compare players"]
)


# -------------------------
# LOAD DATA
# -------------------------

@st.cache_data
def load_summary():
    df = pd.read_parquet("data/summary_stats.parquet")

    if "year" in df.columns:
        df["year"] = df["year"].astype(str)

    return df

@st.cache_data
def load_players():
    players = pd.read_parquet("data/players_stats.parquet")

    if "year" in players.columns:
        players["year"] = players["year"].astype(str)

    return players

df = load_summary()
players_enriched = load_players()


# Beräkna impact90 om den inte finns
if 'impact90' not in players_enriched.columns:
    players_enriched['impact90'] = players_enriched['plus_minus_per90']

if 'impact90' not in df.columns:
    df['impact90'] = df['pm90']

# -------------------------
# SIDEBAR FILTERS
# -------------------------

st.sidebar.header("Filters")

# YEAR FILTER
if "year" in df.columns and "year" in players_enriched.columns:
    available_years = sorted(df["year"].dropna().unique().tolist(), reverse=True)
    
    selected_years = st.sidebar.multiselect(
        "📅 Välj säsong(er)",
        options=available_years,
        default=[available_years[0]] if available_years else []
    )
else:
    selected_years = None

# TEAM FILTER
if "team" in df.columns and "team" in players_enriched.columns:
    # Filtrera teams baserat på valda år först
    if selected_years:
        available_teams = sorted(df[df["year"].isin(selected_years)]["team"].dropna().unique().tolist())
    else:
        available_teams = sorted(df["team"].dropna().unique().tolist())
    
    selected_teams = st.sidebar.multiselect(
        "⚽ Välj lag",
        options=available_teams,
        default=["IK Brage"] if "IK Brage" in available_teams else (
            [available_teams[0]] if available_teams else []
        )
    )
else:
    selected_teams = None

# Name search
name_search = st.sidebar.text_input("🔍 Search player")

# Position filter
if "position" in df.columns:
    positions = ["All"] + sorted(df["position"].dropna().unique().tolist())
    position_filter = st.sidebar.selectbox("📍 Position", positions)
else:
    position_filter = "All"

# Minimum minutes
if "minuter" in df.columns:
    min_minutes = st.sidebar.slider(
        "⏱️ Minimum minutes",
        min_value=0,
        max_value=int(df["minuter"].max()),
        value=0,
        step=100
    )
else:
    min_minutes = 0

# -------------------------
# APPLY FILTERS
# -------------------------

filtered_df = df.copy()
filtered_players = players_enriched.copy()

# Year filter
if selected_years:
    filtered_df = filtered_df[filtered_df["year"].isin(selected_years)]
    filtered_players = filtered_players[filtered_players["year"].isin(selected_years)]

# Team filter
if selected_teams:
    filtered_df = filtered_df[filtered_df["team"].isin(selected_teams)]
    filtered_players = filtered_players[filtered_players["team"].isin(selected_teams)]

if name_search:
    filtered_df = filtered_df[
        filtered_df["name"].str.contains(name_search, case=False, na=False)
    ]

if position_filter != "All":
    filtered_df = filtered_df[filtered_df["position"] == position_filter]

if "minuter" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["minuter"] >= min_minutes]


with tab_overview:
    # -------------------------
    # COLUMN SELECTION
    # -------------------------

    st.subheader("Player summary")

    default_cols = [
        "name", "team", "position", "year", "minuter", "matcher",
        "usage_rate", "starter_rate",
        "impact_combo90", "pm90", "gf90", "ga90"
    ]

    available_cols = [c for c in default_cols if c in filtered_df.columns]

    selected_cols = st.multiselect(
        "Columns to display",
        options=filtered_df.columns.tolist(),
        default=available_cols
    )


    # -------------------------
    # DISPLAY TABLE
    # -------------------------
    st.dataframe(
        filtered_df[selected_cols].sort_values(
            by="usage_rate", ascending=False, na_position="last"
        ),
        use_container_width=True,
        height=450
    )

    # -------------------------
    # DISPLAY MEAN VS STD IMPACT
    # -------------------------

    st.subheader("Impact vs Consistency")

    min_minutes_scatter = st.slider(
        "Min totala minuter spelade",
        min_value=0,
        max_value=1500,
        value=300,
        step=50,
        key="min_minutes_scatter"
    )

    metric_options = {
        "Combined Impact 90": "impact_combo90",
        "Impact per 90": "impact90",
        "Plus-minus per 90": "plus_minus_per90",
        "On/Off per 90": "on_off_diff"
    }

    selected_metric = st.selectbox(
        "Välj impact-mått",
        options=list(metric_options.keys())
    )

    metric = metric_options[selected_metric]

    # Använd filtered_players istället för att hardcoda team
    impact_summary = (
        filtered_players
        .groupby("name")
        .agg(
            impact_mean=(metric, "mean"),
            impact_std=(metric, "std"),
            matches_used=(metric, "count"),
            minutes_total=("minutes_played", "sum")
        )
        .reset_index()
    )

    impact_summary = impact_summary[
        (impact_summary["minutes_total"] >= min_minutes_scatter) &
        (~impact_summary["impact_mean"].isna())
    ]

    if len(impact_summary) > 0:
        fig = px.scatter(
            impact_summary,
            x="impact_std",
            y="impact_mean",
            size="minutes_total",
            hover_name="name",
            title="Impact vs Consistency",
            labels={
                "impact_std": "Variability (std dev)",
                "impact_mean": f"Average {selected_metric}"
            }
        )

        fig.add_hline(y=impact_summary["impact_mean"].median(), line_dash="dash", line_color = "white")
        fig.add_vline(x=impact_summary["impact_std"].median(), line_dash="dash", line_color = "white")

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Ingen data tillgänglig för de valda filtren")

with tab_profile:

    # -------------------------
    # SELECT PLAYER FOR PLAYER VIEW 
    # -------------------------

    st.subheader("Select player")

    player_names = filtered_df["name"].sort_values().tolist()

    if len(player_names) == 0:
        st.warning("Inga spelare matchar de valda filtren")
    else:
        selected_player = st.selectbox(
            "Click to open player profile",
            options=player_names,
            index=6
        )

        st.caption(f"Showing {len(filtered_df)} players")

        st.divider()
        st.header(f"🧑‍💼 Player profile – {selected_player}")

        player_row = filtered_df[filtered_df["name"] == selected_player].iloc[0]

        # --- BASIC INFO ---
        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Team", player_row.get("team"))
        c2.metric("Position", player_row.get("position"))

        age = player_row.get("ålder")
        c3.metric("Year", "–" if pd.isna(age) else f"{int(age)}")

        c4.metric("Minutes", int(player_row.get("minuter")))

        mv = player_row.get("market_value")
        c5.metric("Market value", "–" if pd.isna(mv) else f"{int(mv)}")

        # --- AVAILABILITY ---
        st.subheader("Availability")

        c1, c2, c3 = st.columns(3)
        c1.metric("Matches", int(player_row.get("matcher")))
        c2.metric("Usage rate", round(player_row.get("usage_rate", 0), 2))
        c3.metric("Starter rate", round(player_row.get("starter_rate", 0), 2))

        # --- IMPACT ---
        st.subheader("Impact")

        c1, c2, c3 = st.columns(3)
        c1.metric("Impact / 90", round(player_row.get("impact90", 0), 2))
        c2.metric("Plus-minus / 90", round(player_row.get("pm90", 0), 2))
        c3.metric("On-Off diff", round(player_row.get("on_off_total", 0), 2))

        # -------------------------
        # MATCH LOG PLOT
        # -------------------------

        st.subheader("📅 Match usage")

        player_name = selected_player

        # Använd filtered_players här också
        m = filtered_players[
            filtered_players["name"] == player_name
        ].copy()

        m = m.sort_values("match_start_datetime")

        # säkerställ numeriskt
        m["start_minute"] = m["start_minute"].astype(float)
        m["end_minute"] = m["end_minute"].astype(float)
        m["minutes_played"] = m["minutes_played"].astype(float)

        if len(m) > 0:
            fig = px.bar(
                m,
                x="match_id_short",
                y="minutes_played",
                color="player_type",
                hover_data=[
                    "minutes_played",
                    "start_minute",
                    "end_minute",
                    "goals",
                    "assists",
                    "plus_minus_impact"
                ],
            )

            fig.update_yaxes(
                title="Minutes played",
                range=[0, m["match_length"].max()]
            )

            fig.update_layout(
                title=f"Minutes per match – {player_name}",
                xaxis_tickangle=-45,
                height=450,
                legend_title="Role"
            )

            # referenslinjer
            fig.add_hline(y=45, line_dash="dash", annotation_text="45", line_color = "white")
            fig.add_hline(y=90, line_dash="dash", annotation_text="90", line_color = "white")

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingen matchdata tillgänglig för de valda filtren")

        st.divider()

        # -------------------------
        # IMPACT PER MATCH PLOT 
        # -------------------------

        st.subheader("⚡ Match impact")

        player_data = filtered_players[
            filtered_players["name"] == player_name
        ].sort_values("match_start_datetime").copy()

        if len(player_data) > 0:
            fig = px.line(
                player_data,
                x="match_id_short",
                # y="plus_minus_impact",
                y = "impact_combo90",
                markers=True,
                hover_data=[
                    "minutes_played",
                    "goals",
                    "assists",
                    "yellow_card",
                    "red_card",
                    "plus_minus_raw"
                    # ,"gf_on", "ga_on"
                ]
            )

            fig.update_layout(
                title="Impact per match",
                xaxis_title="",
                yaxis_title="Impact",
                xaxis_tickangle=-45,
                height=400
            )

            # nollinje
            fig.add_hline(
                y=0,
                line_dash="dash",
                line_color="gray",
                annotation_text="Neutral"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingen matchdata tillgänglig")

        st.divider()

        # -------------------------
        # OFFENSIVE IMPACT PER MATCH
        # -------------------------
        
        st.subheader("🛡️ Offensive impact")

        player_data = (filtered_players[filtered_players["name"] == player_name]
            [['match_start_datetime', 'match_id_short', 'name', 'player_type', 'minutes_played', 'goals',
            'assists', 'gf_on', 'ga_on', 'plus_minus_raw', 'on_goal_diff', 'off_goal_diff',
            'yellow_card', 'red_card']]
            .sort_values("match_start_datetime")
        ).copy()

        if len(player_data) > 0:
            fig = px.line(player_data, x = "match_id_short", y = "gf_on",
                        markers = True)

            fig.update_layout(
                xaxis_title="",
                yaxis_title="GF-on",
                xaxis_tickangle=-45,
                legend_title = ""
            )

            st.plotly_chart(fig, use_container_width=True)

        # -------------------------
        # DEFENSIV IMPACT PER MATCH
        # -------------------------
        
        st.subheader("🛡️ Defensive impact")

        player_data = (filtered_players[filtered_players["name"] == player_name]
            [['match_start_datetime', 'match_id_short', 'name', 'player_type', 'minutes_played', 'goals',
            'assists', 'gf_on', 'ga_on', 'plus_minus_raw', 'on_goal_diff', 'off_goal_diff',
            'yellow_card', 'red_card']]
            .sort_values("match_start_datetime")
        ).copy()

        if len(player_data) > 0:
            fig = px.line(player_data, x = "match_id_short", y = "ga_on",
                        markers = True)

            fig.update_layout(
                xaxis_title="",
                yaxis_title="GA-on",
                xaxis_tickangle=-45,
                legend_title = ""
            )

            st.plotly_chart(fig, use_container_width=True)

with tab_compare:
    # -------------------------
    # PLAYERS COMPARISON
    # -------------------------

    players = st.multiselect(
        "Välj spelare att jämföra",
        options=filtered_df["name"].unique(),
        default=["Alexander Zetterström", "Amar Muhsin", "Gustav Nordh"] if all(
            name in filtered_df["name"].values for name in ["Alexander Zetterström", "Amar Muhsin", "Gustav Nordh"]
        ) else []
    )

    cmp = filtered_df[filtered_df["name"].isin(players)].copy()

    if len(players) > 5:
        st.warning("Välj max 5 spelare för tydlig jämförelse")

    if len(players) > 0:
        fig_avail = px.bar(
            cmp.sort_values("usage_rate"),
            y="name",
            x=["usage_rate", "starter_rate"],
            orientation="h",
            barmode="group",
            title="Availability – usage & starter rate",
            labels={"value": "Rate", "variable": "Metric"}
        )

        fig_avail.update_layout(
            xaxis_range=[0, 1],
            height=350
        )

        st.plotly_chart(fig_avail, use_container_width=True)

        fig_off = px.bar(
            cmp.sort_values("mål"),
            y="name",
            x=["mål", "assists"],
            orientation="h",
            barmode="group",
            title="Offensive production"
        )

        st.plotly_chart(fig_off, use_container_width=True)

        fig_def = px.bar(
            cmp.sort_values("ga90"),
            y="name",
            x=["ga90", "clean_sheet_rate"],
            orientation="h",
            barmode="group",
            title="Defensive reliability (per 90)"
        )

        st.plotly_chart(fig_def, use_container_width=True)


        fig_impact = px.bar(
            cmp.sort_values("impact90"),
            y="name",
            x="impact90",
            orientation="h",
            title="Impact per 90 minutes"
        )

        fig_impact.add_vline(x=0, line_dash="dash")

        st.plotly_chart(fig_impact, use_container_width=True)


        metrics = ["usage_rate", "gf90", "ga90", "impact_combo90"]

        radar_df = cmp.set_index("name")[metrics]

        fig_radar = go.Figure()

        for player in radar_df.index:
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=radar_df.loc[player],
                    theta=metrics,
                    fill="toself",
                    name=player
                )
            )

        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True)),
            title="Player profile comparison"
        )

        st.plotly_chart(fig_radar, use_container_width=True)


        default_cols_pc = [
            "name", "team", "position", "year", "minuter", "matcher",
            "usage_rate", "starter_rate",
            "impact90", "pm90", "gf90", "ga90"
        ]

        available_cols_pc = [c for c in default_cols_pc if c in filtered_df.columns]

        selected_cols_pc = st.multiselect(
            "Columns to display",
            options=filtered_df.columns.tolist(),
            default=available_cols_pc,
            key="columns_to_display_pc"

        )

        st.dataframe(
            filtered_df[filtered_df["name"].isin(players)][selected_cols_pc]
                .sort_values(
                    "usage_rate",
                    ascending=False,
                    na_position="last"
                ),
            use_container_width=True,
            height=250
        )
    else:
        st.info("Välj minst en spelare för att jämföra")
