/* Analysis entry point only: controller_step remains the implementation under study. */
#include "__fc_builtin.h"
#include "controller.c"

int main(void)
{
    struct controller_state state = {
        .inlet_valve_open = Frama_C_interval(0, 1)
    };
    float reported_level_pct = Frama_C_float_interval(0.0f, 100.0f);
    return controller_step(reported_level_pct, &state);
}
