"""
core/algorithms/ga_deap.py
==========================
Genetic Algorithm benchmark using the DEAP framework.

Encoding : permutation of customer indices
Crossover: Order Crossover (OX)
Mutation : Shuffle-Indexes
Selection: Tournament selection (size=3)
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np


class GADEAPSolver:
    """
    GA solver built on DEAP for VRP benchmarking.

    Parameters
    ----------
    pop_size        : population size
    n_gen           : number of generations
    cx_prob         : crossover probability
    mut_prob        : mutation probability
    capacity        : vehicle capacity
    emission_factor : kg CO₂ per km
    """

    def __init__(
        self,
        pop_size:        int   = 100,
        n_gen:           int   = 300,
        cx_prob:         float = 0.8,
        mut_prob:        float = 0.2,
        capacity:        float = 100.0,
        w_time:          float = 0.4,
        w_dist:          float = 0.3,
        w_co2:           float = 0.1,
        emission_factor: float = 0.21,
    ) -> None:
        self.pop_size        = pop_size
        self.n_gen           = n_gen
        self.cx_prob         = cx_prob
        self.mut_prob        = mut_prob
        self.capacity        = capacity
        self.w_time          = w_time
        self.w_dist          = w_dist
        self.w_co2           = w_co2
        self.emission_factor = emission_factor

    # ------------------------------------------------------------------
    def _decode(self, individual, customers, demands):
        routes: List[List[int]] = [[]]
        load = 0.0
        for idx in individual:
            cust = customers[idx]
            d    = demands.get(cust, 0)
            if load + d > self.capacity:
                routes.append([])
                load = 0.0
            routes[-1].append(cust)
            load += d
        return [r for r in routes if r]

    def _route_metrics(self, route, graph, depot=0):
        seq = [depot] + route + [depot]
        tt = td = 0.0
        for i in range(len(seq) - 1):
            try:
                path = nx.shortest_path(graph, seq[i], seq[i+1], weight="weight")
                for a, b in zip(path, path[1:]):
                    tt += graph[a][b].get("travel_time", 0)
                    td += graph[a][b].get("distance", 0)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                tt += 1e6
        return tt, td

    def _eval(self, individual, graph, customers, demands):
        routes = self._decode(individual, customers, demands)
        tt = td = co2 = 0.0
        for r in routes:
            t, d = self._route_metrics(r, graph)
            tt  += t
            td  += d
            co2 += d * self.emission_factor
        cost = self.w_time*tt + self.w_dist*td + self.w_co2*co2
        return (cost,)   # DEAP expects a tuple

    # ------------------------------------------------------------------
    def optimize(self, graph, customers, demands, depot=0, verbose=False):
        try:
            from deap import base, creator, tools, algorithms
        except ImportError:
            raise ImportError("Install DEAP: pip install deap")

        n = len(customers)

        # ── DEAP setup (guard against re-creation in same process) ──
        if not hasattr(creator, "FitnessMinGA"):
            creator.create("FitnessMinGA", base.Fitness, weights=(-1.0,))
        if not hasattr(creator, "IndividualGA"):
            creator.create("IndividualGA", list, fitness=creator.FitnessMinGA)

        toolbox = base.Toolbox()
        toolbox.register("indices",    random.sample, range(n), n)
        toolbox.register("individual", tools.initIterate,
                         creator.IndividualGA, toolbox.indices)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("evaluate",   self._eval,
                         graph=graph, customers=customers, demands=demands)
        toolbox.register("mate",       tools.cxOrdered)
        toolbox.register("mutate",     tools.mutShuffleIndexes, indpb=0.05)
        toolbox.register("select",     tools.selTournament, tournsize=3)

        pop = toolbox.population(n=self.pop_size)
        hof = tools.HallOfFame(1)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("min", np.min)

        history: List[float] = []

        # Evaluate initial population
        fitnesses = list(map(toolbox.evaluate, pop))
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit

        hof.update(pop)

        for gen in range(self.n_gen):
            offspring = toolbox.select(pop, len(pop))
            offspring = list(map(toolbox.clone, offspring))

            # Crossover
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.cx_prob:
                    toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            # Mutation
            for mutant in offspring:
                if random.random() < self.mut_prob:
                    toolbox.mutate(mutant)
                    del mutant.fitness.values

            # Evaluate invalid individuals
            invalid = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = list(map(toolbox.evaluate, invalid))
            for ind, fit in zip(invalid, fitnesses):
                ind.fitness.values = fit

            pop[:] = offspring
            hof.update(pop)
            history.append(hof[0].fitness.values[0])

            if verbose and gen % 50 == 0:
                print(f"  GA   gen  {gen:4d} | best fitness = {history[-1]:.4f}")

        best_routes = self._decode(list(hof[0]), customers, demands)
        return best_routes, hof[0].fitness.values[0], history
