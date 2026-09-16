#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

#define LOW_LEVEL_PCT 45.0f
#define HIGH_LEVEL_PCT 55.0f

struct controller_state {
    bool inlet_valve_open;
};

bool controller_step(float reported_level_pct, struct controller_state *state)
{
    if (reported_level_pct < LOW_LEVEL_PCT) {
        state->inlet_valve_open = true;
    } else if (reported_level_pct > HIGH_LEVEL_PCT) {
        state->inlet_valve_open = false;
    }
    return state->inlet_valve_open;
}

/* The small runner exists only for semantic-equivalence tests. */
#ifdef HW2_SEQUENCE_RUNNER
int main(int argc, char **argv)
{
    struct controller_state state = {false};
    int index;

    for (index = 1; index < argc; index++) {
        float reported = strtof(argv[index], NULL);
        printf("%d\n", controller_step(reported, &state) ? 1 : 0);
    }
    return 0;
}
#endif
