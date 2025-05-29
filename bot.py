

import os
import asyncio
import logging
from types import SimpleNamespace
from asgiref.sync import sync_to_async
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()
from core.models import TgUser, Subject, Task, PlanText

#Базовые настройки
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8174780325:AAF6EyldUs0bBxQ4pNryhB-Ko0onZpCfKCo" 
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

#FSM
class RegFSM(StatesGroup):
    start = State()
    reg_choice = State()
    exam = State()
    class_level = State()
    subjects_selecting = State()
    subject_goal = State()
    trial_score = State()
    days_left = State()
    main_menu = State()

# Хелперы
def main_kb():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Подготовка", callback_data="menu_prep")],
            [types.InlineKeyboardButton(text="Поиск материалов", callback_data="menu_search")],
            [types.InlineKeyboardButton(text="Профиль", callback_data="menu_profile")],
            [types.InlineKeyboardButton(text="Психологическая поддержка", callback_data="menu_support")],
        ]
    )

async def show_main_menu(target, state: FSMContext):
    text = "Главное меню:\n\nВыберите раздел."
    if isinstance(target, types.Message):
        await target.answer(text, reply_markup=main_kb())
    else:
        await target.message.answer(text, reply_markup=main_kb())
    await state.set_state(RegFSM.main_menu)

#/start
@dp.message(CommandStart())
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    txt = (
        "<b>Экзаменационный бот</b>\n\n"
        "• Персональный план подготовки\n"
        "• Отслеживание прогресса\n"
        "• Психологическая поддержка\n"
        "• Поиск материалов\n\n"
        "<b>Начать работу:</b>"
    )
    await msg.answer(txt, reply_markup=types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="Начать", callback_data="start_reg")]]
    ))
    await state.set_state(RegFSM.start)

@dp.callback_query(RegFSM.start, F.data == "start_reg")
async def choose_reg(call: types.CallbackQuery, state: FSMContext):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Пройти регистрацию", callback_data="reg_start")],
            [types.InlineKeyboardButton(text="Пропустить", callback_data="reg_skip")],
        ]
    )
    await call.message.edit_text(
        "Рекомендуем пройти регистрацию для персонального плана.",
        reply_markup=kb,
    )
    await state.set_state(RegFSM.reg_choice)

@dp.callback_query(RegFSM.reg_choice, F.data == "reg_skip")
async def reg_skip(call: types.CallbackQuery, state: FSMContext):
    user, _ = await sync_to_async(TgUser.objects.get_or_create)(
        tg_id=call.from_user.id, defaults={"name": call.from_user.full_name}
    )
    user.is_registered = False
    await sync_to_async(user.save)()
    await call.message.edit_text("Вы пропустили регистрацию.")
    await show_main_menu(call, state)
    await state.set_state(RegFSM.main_menu)

# Экзамен
@dp.callback_query(RegFSM.reg_choice, F.data == "reg_start")
async def ask_exam(call: types.CallbackQuery, state: FSMContext):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="ОГЭ", callback_data="exam_OGE")],
            [types.InlineKeyboardButton(text="ЕГЭ", callback_data="exam_EGE")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_reg_choice")],
        ]
    )
    await call.message.edit_text("Что вы сдаёте?", reply_markup=kb)
    await state.set_state(RegFSM.exam)

@dp.callback_query(RegFSM.exam, F.data == "back_reg_choice")
async def back_to_reg_choice(call: types.CallbackQuery, state: FSMContext):
    await choose_reg(call, state)



# Класс
@dp.callback_query(RegFSM.exam, F.data.startswith("exam_"))
async def choose_class(call: types.CallbackQuery, state: FSMContext):
    exam = call.data.split("_")[1]
    await state.update_data(exam_type=exam)

    if exam == "OGE":
        options = [["8 и ниже", "class_8"], ["9 класс", "class_9"]]
    else:
        options = [["10 класс", "class_10"], ["11 класс", "class_11"]]
    kb_rows = [[types.InlineKeyboardButton(text=txt, callback_data=cd)] for txt, cd in options]
    kb_rows.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_exam")])

    await call.message.edit_text(
        "В каком классе вы учитесь?",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )
    await state.set_state(RegFSM.class_level)

@dp.callback_query(RegFSM.class_level, F.data == "back_exam")
async def class_back(call: types.CallbackQuery, state: FSMContext):
    await ask_exam(call, state)

#выбор предметов (с галочками)
async def redraw_subjects(call: types.CallbackQuery | types.Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_subjects", [])
    subjects = await sync_to_async(list)(Subject.objects.all())
    rows, row = [], []
    for idx, subj in enumerate(subjects, 1):
        mark = " ✅" if subj.id in selected else ""
        row.append(types.InlineKeyboardButton(text=subj.title + mark, callback_data=f"subj_{subj.id}"))
        if idx % 3 == 0 or idx == len(subjects):
            rows.append(row)
            row = []
    rows.append([types.InlineKeyboardButton(text="Готово", callback_data="subjects_done")])
    rows.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_class")])

    kb = types.InlineKeyboardMarkup(inline_keyboard=rows)
    text = "Выберите предметы (повторное нажатие — снять выбор):"
    if isinstance(call, types.CallbackQuery):
        await call.message.edit_text(text, reply_markup=kb)
    else:
        await call.answer(text, reply_markup=kb)
    await state.set_state(RegFSM.subjects_selecting)

@dp.callback_query(RegFSM.class_level, F.data.startswith("class_"))
async def after_class(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(class_level=call.data.split("_")[1], selected_subjects=[])
    await redraw_subjects(call, state)

@dp.callback_query(RegFSM.subjects_selecting, F.data.startswith("subj_"))
async def toggle_subject(call: types.CallbackQuery, state: FSMContext):
    sid = int(call.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("selected_subjects", [])
    selected.remove(sid) if sid in selected else selected.append(sid)
    await state.update_data(selected_subjects=selected)
    await redraw_subjects(call, state)

@dp.callback_query(RegFSM.subjects_selecting, F.data == "back_class")
async def subjects_back(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    exam = data["exam_type"]
    fake = SimpleNamespace(data=f"exam_{exam}", from_user=call.from_user, message=call.message)
    await choose_class(fake, state)

@dp.callback_query(RegFSM.subjects_selecting, F.data == "subjects_done")
async def finish_subjects(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected_subjects"):
        await call.answer("Нужно выбрать хотя бы один предмет!", show_alert=True)
        return
    await state.update_data(subject_index=0, subject_goals={}, trial_scores={})
    await ask_goal_for_current_subject(call, state)


async def ask_goal_for_current_subject(call, state: FSMContext):
    data = await state.get_data()
    idx = data.get("subject_index", 0)
    subjects = data["selected_subjects"]
    if idx >= len(subjects):
        await finalize_registration(call, state)
        return
    subject = await sync_to_async(Subject.objects.get)(id=subjects[idx])
    exam_type = data["exam_type"]
    kb = []
    if exam_type == "OGE":
        kb = [
            types.InlineKeyboardButton(text="3", callback_data="goal_3"),
            types.InlineKeyboardButton(text="4", callback_data="goal_4"),
            types.InlineKeyboardButton(text="5", callback_data="goal_5"),
        ]
    elif exam_type == "EGE":
        kb = [
            types.InlineKeyboardButton(text="60", callback_data="goal_60"),
            types.InlineKeyboardButton(text="70", callback_data="goal_70"),
            types.InlineKeyboardButton(text="80", callback_data="goal_80"),
            types.InlineKeyboardButton(text="90", callback_data="goal_90"),
            types.InlineKeyboardButton(text="100", callback_data="goal_100"),
        ]
    kb_back = [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_goal")]
    await call.message.edit_text(
        f"<b>{subject.title}</b>\n\nКакой балл вы хотите получить?",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[kb, kb_back]),
        parse_mode="HTML"
    )
    await state.set_state(RegFSM.subject_goal)

@dp.callback_query(RegFSM.subject_goal, F.data == "back_goal")
async def back_goal(call: types.CallbackQuery, state: FSMContext):
    await redraw_subjects(call, state)

@dp.callback_query(RegFSM.subject_goal, F.data.startswith("goal_"))
async def ask_trial_for_current_subject(call: types.CallbackQuery, state: FSMContext):
    goal = call.data.split("_")[1]
    data = await state.get_data()
    subjects = data["selected_subjects"]
    index = data.get("subject_index", 0)
    goals = data.get("subject_goals", {})
    subj_id = subjects[index]
    goals[str(subj_id)] = goal
    await state.update_data(subject_goals=goals)
    subj = await sync_to_async(Subject.objects.get)(id=subj_id)
    exam_type = data["exam_type"]
    subj_title = subj.title.lower()
    kb_back = [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_goal")]
    buttons = [types.InlineKeyboardButton(text="Не писал", callback_data="trial_0")]
    if exam_type == "OGE":
        if "матем" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="8-14", callback_data="trial_8-14"),
                types.InlineKeyboardButton(text="15-21", callback_data="trial_15-21"),
                types.InlineKeyboardButton(text="22-31", callback_data="trial_22-31"),
            ]
        elif "рус" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="15-25", callback_data="trial_15-25"),
                types.InlineKeyboardButton(text="26-32", callback_data="trial_26-32"),
                types.InlineKeyboardButton(text="33-37", callback_data="trial_33-37"),
            ]
    elif exam_type == "EGE":
        if "матем" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="27-40", callback_data="trial_27-40"),
                types.InlineKeyboardButton(text="41-60", callback_data="trial_41-60"),
                types.InlineKeyboardButton(text="61-80", callback_data="trial_61-80"),
                types.InlineKeyboardButton(text="81-90", callback_data="trial_81-90"),
                types.InlineKeyboardButton(text="91-100", callback_data="trial_91-100"),
            ]
        elif "рус" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="36-50", callback_data="trial_36-50"),
                types.InlineKeyboardButton(text="51-70", callback_data="trial_51-70"),
                types.InlineKeyboardButton(text="71-80", callback_data="trial_71-80"),
                types.InlineKeyboardButton(text="81-90", callback_data="trial_81-90"),
                types.InlineKeyboardButton(text="91-100", callback_data="trial_91-100"),
            ]
    await call.message.edit_text(
        "Сколько баллов вы набрали на пробнике?",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[buttons, kb_back]
        )
    )
    await state.set_state(RegFSM.trial_score)

@dp.callback_query(RegFSM.trial_score, F.data == "back_goal")
async def back_to_goal(call: types.CallbackQuery, state: FSMContext):
    await ask_goal_for_current_subject(call, state)

@dp.callback_query(RegFSM.trial_score, F.data.startswith("trial_"))
async def ask_days_for_current_subject(call: types.CallbackQuery, state: FSMContext):
    trial = call.data.split("_")[1]
    data = await state.get_data()
    subjects = data["selected_subjects"]
    index = data.get("subject_index", 0)
    trial_scores = data.get("trial_scores", {})
    subj_id = subjects[index]
    trial_scores[str(subj_id)] = trial
    await state.update_data(trial_scores=trial_scores)
    if index + 1 < len(subjects):
        await state.update_data(subject_index=index + 1)
        await ask_goal_for_current_subject(call, state)
    else:
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text=">300", callback_data="days_300"),
                    types.InlineKeyboardButton(text="200-300", callback_data="days_200"),
                    types.InlineKeyboardButton(text="100-200", callback_data="days_100"),
                    types.InlineKeyboardButton(text="<100", callback_data="days_99"),
                ],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_trial")]
            ]
        )
        await call.message.edit_text(
            "Сколько дней осталось до экзамена?",
            reply_markup=kb
        )
        await state.set_state(RegFSM.days_left)

@dp.callback_query(RegFSM.days_left, F.data == "back_trial")
async def back_to_trial_from_days(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("subject_index", 0)
    subjects = data["selected_subjects"]
    subj_id = subjects[idx]
    subj = await sync_to_async(Subject.objects.get)(id=subj_id)
    exam_type = data["exam_type"]
    subj_title = subj.title.lower()
    buttons = [types.InlineKeyboardButton(text="Не писал", callback_data="trial_0")]
    if exam_type == "OGE":
        if "матем" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="8-14", callback_data="trial_8-14"),
                types.InlineKeyboardButton(text="15-21", callback_data="trial_15-21"),
                types.InlineKeyboardButton(text="22-31", callback_data="trial_22-31"),
            ]
        elif "рус" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="15-25", callback_data="trial_15-25"),
                types.InlineKeyboardButton(text="26-32", callback_data="trial_26-32"),
                types.InlineKeyboardButton(text="33-37", callback_data="trial_33-37"),
            ]
    elif exam_type == "EGE":
        if "матем" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="27-40", callback_data="trial_27-40"),
                types.InlineKeyboardButton(text="41-60", callback_data="trial_41-60"),
                types.InlineKeyboardButton(text="61-80", callback_data="trial_61-80"),
                types.InlineKeyboardButton(text="81-90", callback_data="trial_81-90"),
                types.InlineKeyboardButton(text="91-100", callback_data="trial_91-100"),
            ]
        elif "рус" in subj_title:
            buttons += [
                types.InlineKeyboardButton(text="36-50", callback_data="trial_36-50"),
                types.InlineKeyboardButton(text="51-70", callback_data="trial_51-70"),
                types.InlineKeyboardButton(text="71-80", callback_data="trial_71-80"),
                types.InlineKeyboardButton(text="81-90", callback_data="trial_81-90"),
                types.InlineKeyboardButton(text="91-100", callback_data="trial_91-100"),
            ]
    kb_back = [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_goal")]
    await call.message.edit_text(
        "Сколько баллов вы набрали на пробнике?",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[buttons, kb_back])
    )
    await state.set_state(RegFSM.trial_score)

@dp.callback_query(RegFSM.days_left, F.data.startswith("days_"))
async def save_days_and_finish(call: types.CallbackQuery, state: FSMContext):
    days = call.data.split("_")[1]
    data = await state.get_data()
    days_left = data.get("days_left_all", {})
    subjects = data["selected_subjects"]
    idx = data.get("subject_index", 0)
    subj_id = subjects[idx]
    days_left[str(subj_id)] = days
    await state.update_data(days_left_all=days_left)
    await finalize_registration(call, state)

#Завершение регистрации
async def finalize_registration(msg_or_call, state: FSMContext):
    data = await state.get_data()
    user, _ = await sync_to_async(TgUser.objects.get_or_create)(
        tg_id=msg_or_call.from_user.id,
        defaults={"name": msg_or_call.from_user.full_name}
    )
    user.is_registered = True
    user.exam_type = data.get("exam_type")
    user.class_level = data.get("class_level")
    user.subject_goals = data.get("subject_goals", {})
    user.trial_scores = data.get("trial_scores", {})
    user.days_left = str(data.get("days_left_all", {}))
    await sync_to_async(user.save)()
    subjects = [int(x) for x in data.get("selected_subjects", [])]
    await sync_to_async(user.subjects.set)(subjects)
    await sync_to_async(user.save)()
    await show_main_menu(msg_or_call, state)

async def get_plan_text(exam_type, subject, desired_score, trial_score):
    plan = await sync_to_async(PlanText.objects.filter(
        exam_type=exam_type,
        subject=subject,
        desired_score=desired_score,
        trial_score=trial_score
    ).first)()
    return plan.text if plan else f"План для {subject} не найден"

#Профиль
@dp.callback_query(RegFSM.main_menu, F.data == "menu_profile")
async def menu_profile(call: types.CallbackQuery, state: FSMContext):
    user = await sync_to_async(TgUser.objects.get)(tg_id=call.from_user.id)
    if not user.is_registered:
        await call.message.edit_text(
            "Профиль не создан. Пройдите регистрацию.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="Пройти регистрацию", callback_data="reg_start")],
                    [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
                ]
            ),
        )
        await state.set_state(RegFSM.reg_choice)
        return

    subj_goals = user.subject_goals or {}
    subjects_info = []
    for subj in await sync_to_async(list)(user.subjects.all()):
        goal = subj_goals.get(str(subj.id), "—")
        subjects_info.append(f"{subj.title} — {goal}")
    subjects = "\n".join(subjects_info) or "—"

    profile = (
        f"<b>Экзамен:</b> {user.exam_type or '—'}\n"
        f"<b>Класс:</b> {user.class_level or '—'}\n"
        f"<b>Предметы и желаемые баллы:</b>\n{subjects}\n"
        f"<b>Уведомления:</b> {'Включены' if user.notify_time else 'Отключены'}"
    )
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Изменить экзамен", callback_data="edit_exam")],
            [types.InlineKeyboardButton(text="Изменить класс", callback_data="edit_class")],
            [types.InlineKeyboardButton(text="Изменить предметы", callback_data="edit_subjects")],
            [types.InlineKeyboardButton(text="Настроить уведомления", callback_data="edit_notify")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )
    await call.message.edit_text(profile, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(RegFSM.main_menu, F.data == "back_main")
async def back_from_profile(call: types.CallbackQuery, state: FSMContext):
    await show_main_menu(call, state)


@dp.callback_query(RegFSM.main_menu, F.data == "edit_exam")
async def edit_exam(call: types.CallbackQuery, state: FSMContext):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="ОГЭ", callback_data="save_exam_OGE")],
            [types.InlineKeyboardButton(text="ЕГЭ", callback_data="save_exam_EGE")],
            [types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_profile")],
        ]
    )
    await call.message.edit_text("Выберите экзамен:", reply_markup=kb)

@dp.callback_query(RegFSM.main_menu, F.data.startswith("save_exam_"))
async def save_exam(call: types.CallbackQuery, state: FSMContext):
    new_exam = call.data.split("_")[2]
    user = await sync_to_async(TgUser.objects.get)(tg_id=call.from_user.id)
    # Сброс данных
    user.exam_type, user.class_level = new_exam, None
    await sync_to_async(user.subjects.clear)()
    user.subject_goals, user.trial_scores = {}, {}
    await sync_to_async(user.save)()
    await state.clear()
    await state.update_data(is_change_exam=True)
    # Переход к выбору класса
    if new_exam == "OGE":
        options = [("8 и ниже", "editcls_8"), ("9", "editcls_9")]
    else:
        options = [("10", "editcls_10"), ("11", "editcls_11")]
    rows = [[types.InlineKeyboardButton(txt, callback_data=cb)] for txt, cb in options]
    rows.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")])
    await call.message.edit_text(
        "Выберите класс:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await state.set_state(RegFSM.class_level)

@dp.callback_query(RegFSM.main_menu, F.data == "edit_class")
async def edit_class(call: types.CallbackQuery, state: FSMContext):
    user = await sync_to_async(TgUser.objects.get)(tg_id=call.from_user.id)
    if user.exam_type == "OGE":
        options = [("8 и ниже", "editcls_8"), ("9", "editcls_9")]
    else:
        options = [("10", "editcls_10"), ("11", "editcls_11")]
    rows = [[types.InlineKeyboardButton(txt, callback_data=cb)] for txt, cb in options]
    rows.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")])
    await call.message.edit_text(
        "Выберите класс:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await state.set_state(RegFSM.class_level)

@dp.callback_query(RegFSM.class_level, F.data.startswith("editcls_"))
async def save_class(call: types.CallbackQuery, state: FSMContext):
    cls = call.data.split("_")[1]
    user = await sync_to_async(TgUser.objects.get)(tg_id=call.from_user.id)
    user.class_level = cls
    await sync_to_async(user.save)()
    data = await state.get_data()
    if data.get("is_change_exam"):
        await state.update_data(class_level=cls, selected_subjects=[])
        await redraw_subjects(call, state)
    else:
        await menu_profile(call, state)

@dp.callback_query(RegFSM.main_menu, F.data == "edit_subjects")
async def edit_subjects(call: types.CallbackQuery, state: FSMContext):
    user = await sync_to_async(TgUser.objects.get)(tg_id=call.from_user.id)
    subj_ids = list(await sync_to_async(list)(user.subjects.values_list("id", flat=True)))
    await state.update_data(selected_subjects=subj_ids)
    await redraw_subjects(call, state)

#
async def finalize_registration(msg_or_call, state: FSMContext):
    data = await state.get_data()
    user, _ = await sync_to_async(TgUser.objects.get_or_create)(
        tg_id=msg_or_call.from_user.id,
        defaults={"name": msg_or_call.from_user.full_name}
    )
    user.is_registered = True
    user.exam_type = data.get("exam_type")
    user.class_level = data.get("class_level")
    user.subject_goals = data.get("subject_goals", {})
    user.trial_scores = data.get("trial_scores", {})
    user.days_left = str(data.get("days_left_all", {}))
    await sync_to_async(user.save)()
    subjects = [int(x) for x in data.get("selected_subjects", [])]
    await sync_to_async(user.subjects.set)(subjects)
    await sync_to_async(user.save)()
    await state.clear()
        # ===== ВЫВОД ПЕРСОНАЛЬНОГО ПЛАНА ПО КАЖДОМУ ПРЕДМЕТУ =====
    exam_type = user.exam_type
    subject_goals = user.subject_goals or {}
    trial_scores = user.trial_scores or {}
    # Если subjects — это ids, получаем названия
    subjects_qs = await sync_to_async(list)(user.subjects.all())
    for subj in subjects_qs:
        subj_name = subj.title
        desired_score = subject_goals.get(str(subj.id), "—")
        trial_score = trial_scores.get(str(subj.id), "—")
        text = await get_plan_text(exam_type, subj_name, desired_score, trial_score)
        await msg_or_call.answer(text)

    await show_main_menu(msg_or_call, state)

# Уведомления
@dp.callback_query(RegFSM.main_menu, F.data == "edit_notify")
async def edit_notify(call: types.CallbackQuery, state: FSMContext):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Включить (19:00)", callback_data="notify_on")],
            [types.InlineKeyboardButton(text="Отключить", callback_data="notify_off")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")],
        ]
    )
    await call.message.edit_text("Настройте уведомления:", reply_markup=kb)

@dp.callback_query(RegFSM.main_menu, F.data.in_(["notify_on", "notify_off"]))
async def switch_notify(call: types.CallbackQuery, state: FSMContext):
    user = await sync_to_async(TgUser.objects.get)(tg_id=call.from_user.id)
    user.notify_time = "19:00" if call.data == "notify_on" else None
    await sync_to_async(user.save)()
    await menu_profile(call, state)

# ПСИХОЛОГИЧЕСКАЯ ПОДДЕРЖКА 
@dp.callback_query(RegFSM.main_menu, F.data == "menu_support")
async def menu_support(call: types.CallbackQuery, state: FSMContext):
    text = (
        "<b>Психологическая поддержка</b>\n\n"
        "• Видео для расслабления и дыхания:\n"
        "https://www.youtube.com/watch?v=odADwWzHR24\n"
        "https://www.youtube.com/watch?v=inpok4MKVLM\n"
        "https://www.youtube.com/watch?v=MIr3RsUWrdo\n"
        "\nЕсли тревожно — нажмите кнопку ниже."
    )
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Мне тревожно", callback_data="psych_random")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)

# Список советов 
PSYCH_TIPS = [
    "Попробуйте технику дыхания: вдох — 4 секунды, задержка — 4 секунды, выдох — 4 секунды.",
    "Закройте глаза, сделайте медленный глубокий вдох, затем выдохните напряжение.",
    "Погуляйте на свежем воздухе или сделайте небольшую разминку.",
    "Попробуйте записать свои тревоги на листе и вычеркнуть самые малозначимые.",
    "Выпейте воды и попробуйте сфокусироваться на дыхании 1-2 минуты.",
]

import random

@dp.callback_query(F.data == "psych_random")
async def send_psych_tip(call: types.CallbackQuery, state: FSMContext):
    tip = random.choice(PSYCH_TIPS)
    await call.answer(tip, show_alert=True)

@dp.callback_query(F.data == "back_main")
async def back_to_menu_from_support(call: types.CallbackQuery, state: FSMContext):
    await show_main_menu(call, state)


@dp.callback_query(RegFSM.main_menu, F.data == "menu_search")
async def search_materials_entry(call: types.CallbackQuery, state: FSMContext):
    text = (
        "<b>Поиск материалов</b>\n\n"
        "Введите ключевое слово, тему или номер задания, например:\n"
        "<code>математика вариант</code>\n"
        "<code>егэ биология задание 18</code>\n\n"
        "Скоро здесь появится быстрый поиск по базе теории, видео и заданий."
    )
    await call.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]]
    ))
    await state.set_state(RegFSM.main_menu)

#Подготовка (выбор предмета и типа задания)

@dp.callback_query(RegFSM.main_menu, F.data == "menu_prep")
async def prep_entry(call: types.CallbackQuery, state: FSMContext):
    user = await sync_to_async(TgUser.objects.get)(tg_id=call.from_user.id)
    if not user.is_registered:
        await call.message.edit_text(
            "Для подготовки к предметам пройдите регистрацию.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton("Пройти регистрацию", callback_data="reg_start")],
                                 [types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]]
            )
        )
        await state.set_state(RegFSM.reg_choice)
        return
    # Показываем предметы пользователя
    subjects = list(await sync_to_async(list)(user.subjects.all()))
    kb = []
    for subj in subjects:
        kb.append([types.InlineKeyboardButton(text=subj.title, callback_data=f"prep_subj_{subj.id}")])
    kb.append([types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")])
    await call.message.edit_text(
        "Выберите предмет:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(RegFSM.main_menu)

@dp.callback_query(F.data.startswith("prep_subj_"))
async def prep_choose_task(call: types.CallbackQuery, state: FSMContext):
    subj_id = int(call.data.split("_")[2])
    subject = await sync_to_async(Subject.objects.get)(id=subj_id)
    kb = [
        [types.InlineKeyboardButton("Теория", callback_data=f"task_theory_{subj_id}"),
         types.InlineKeyboardButton("Тренажёр 1", callback_data=f"task_train1_{subj_id}"),
         types.InlineKeyboardButton("Тренажёр 2", callback_data=f"task_train2_{subj_id}")],
        [types.InlineKeyboardButton("Ответы", callback_data=f"task_answers_{subj_id}"),
         types.InlineKeyboardButton("Видео: теория", callback_data=f"task_video_theory_{subj_id}"),
         types.InlineKeyboardButton("Видео: практика", callback_data=f"task_video_practice_{subj_id}")],
        [types.InlineKeyboardButton("🔎 Найти похожие задачи", callback_data=f"find_similar_{subj_id}")],
        [types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_prep")]
    ]
    await call.message.edit_text(
        f"<b>{subject.title}</b>\nВыберите тип материала или тренажёр:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )

# Заглушки для разделов "теория", "тренажёры", "ответы" и т.д.
@dp.callback_query(F.data.startswith("task_"))
async def task_detail(call: types.CallbackQuery, state: FSMContext):
    
    t = call.data.split("_")[1]
    names = {
        "theory": "Теория по предмету.",
        "train1": "Тренажёр: вариант 1.",
        "train2": "Тренажёр: вариант 2.",
        "answers": "Ответы и разбор заданий.",
        "video": "Видео-материал.",
        "video_theory": "Видео по теории.",
        "video_practice": "Видео по практике.",
    }
    await call.answer()
    await call.message.answer(
        f"<b>{names.get(t, 'Раздел в разработке.')}</b>\n\n"
        f"В будущем тут будет подборка материалов и тренажёров."
    )

@dp.callback_query(F.data.startswith("find_similar_"))
async def find_similar_tasks(call: types.CallbackQuery, state: FSMContext):
    
    await call.answer()
    await call.message.answer(
        "🔎 <b>Поиск похожих задач</b>\n\n"
        "Скоро здесь появится умный поиск по базе заданий."
    )

#Заготовка для админки (минимум: переключение режимов и stub)
@dp.message(lambda msg: msg.text == "/admin")
async def admin_mode_entry(msg: types.Message, state: FSMContext):
    # по тг id можно реализовать по идеи
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton("Контент", callback_data="admin_content")],
            [types.InlineKeyboardButton("Рассылки", callback_data="admin_broadcast")],
            [types.InlineKeyboardButton("Аналитика", callback_data="admin_analytics")],
            [types.InlineKeyboardButton("Настройки", callback_data="admin_settings")],
            [types.InlineKeyboardButton("Выйти из админки", callback_data="exit_admin")],
        ]
    )
    await msg.answer("<b>Админ-панель</b>\nВыберите раздел:", reply_markup=kb)
    await state.set_state(RegFSM.main_menu)

@dp.callback_query(F.data.startswith("admin_"))
async def admin_stub(call: types.CallbackQuery, state: FSMContext):
    section = call.data.replace("admin_", "")
    await call.message.edit_text(
        f"<b>Раздел \"{section}\" админ-панели в разработке.</b>\n"
        "Полноценная поддержка будет добавлена в будущем.",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton("⬅️ Назад", callback_data="exit_admin")]]
        )
    )

@dp.callback_query(F.data == "exit_admin")
async def exit_admin(call: types.CallbackQuery, state: FSMContext):
    await show_main_menu(call, state)

# 
@dp.callback_query(F.data.startswith("exam_"))
async def debug_exam_any_state(call: types.CallbackQuery, state: FSMContext):
    await call.answer("Не то состояние FSM. Выберите регистрацию заново!", show_alert=True)

# --- Старт polling ---
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))

