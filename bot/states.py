from aiogram.fsm.state import State, StatesGroup


class Flow(StatesGroup):
    income_amount = State()
    income_comment = State()
    expense_amount = State()
    expense_comment = State()
    pocket = State()
    report_type = State()
    report_day = State()
    period_start = State()
    period_end = State()
    debts_menu = State()
    debt_name = State()
    debt_amount = State()
    debt_comment = State()
    debt_direction = State()
    debt_pay_pick = State()
    debt_pay_amount = State()
    debt_delete_pick = State()
    debt_delete_confirm = State()
    edit_day = State()
    edit_pick = State()
    edit_action = State()
    edit_amount = State()
    edit_comment = State()
    edit_delete_confirm = State()


DEBT_STATES = {
    Flow.debts_menu.state,
    Flow.debt_name.state,
    Flow.debt_amount.state,
    Flow.debt_comment.state,
    Flow.debt_direction.state,
    Flow.debt_pay_pick.state,
    Flow.debt_pay_amount.state,
    Flow.debt_delete_pick.state,
    Flow.debt_delete_confirm.state,
}
