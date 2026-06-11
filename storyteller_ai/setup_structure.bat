@echo off
echo Creating Storyteller AI project structure...

set BASE=storyteller_ai\backend

mkdir storyteller_ai
mkdir %BASE%
mkdir %BASE%\routers
mkdir %BASE%\gm_modes
mkdir %BASE%\engines
mkdir %BASE%\services
mkdir %BASE%\models
mkdir storyteller_ai\scripts

echo Creating placeholder files...

type nul > %BASE%\main.py
type nul > %BASE%\routers\gm.py
type nul > %BASE%\routers\sessions.py
type nul > %BASE%\routers\tools.py
type nul > %BASE%\routers\dashboard.py

type nul > %BASE%\gm_modes\__init__.py
type nul > %BASE%\gm_modes\solo.py
type nul > %BASE%\gm_modes\group.py
type nul > %BASE%\gm_modes\assistant.py
type nul > %BASE%\gm_modes\orchestrator.py
type nul > %BASE%\gm_modes\prompt_wrapper.py
type nul > %BASE%\gm_modes\scene_framing.py

type nul > %BASE%\engines\gm_loop.py
type nul > %BASE%\engines\faction_ai.py
type nul > %BASE%\engines\faction_engine.py
type nul > %BASE%\engines\city_map.py
type nul > %BASE%\engines\npc_memory.py
type nul > %BASE%\engines\secrecy_tracker.py
type nul > %BASE%\engines\chronicle_starter.py
type nul > %BASE%\engines\turn_engine.py
type nul > %BASE%\engines\scene_predictor.py
type nul > %BASE%\engines\pc_builder.py
type nul > %BASE%\engines\combat_engine.py
type nul > %BASE%\engines\dice_pool.py

type nul > %BASE%\services\llm_client.py
type nul > %BASE%\services\llm_response.py
type nul > %BASE%\services\llm_utils.py
type nul > %BASE%\services\retry.py
type nul > %BASE%\services\simulation_service.py
type nul > %BASE%\services\session_manager.py
type nul > %BASE%\services\state_engine.py

type nul > %BASE%\models\schemas.py

type nul > storyteller_ai\README.md

echo Done!
pause
