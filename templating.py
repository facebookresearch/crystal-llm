import os
import argparse
import random
import pandas as pd
import numpy as np
from pymatgen.core import Element
from pymatgen.core.structure import Structure
from m3gnet.models import Relaxer

def find_similar_elements(target_element, elements, tolerance=0.1):
    similar_elements = []
    for state, radius in target_element.ionic_radii.items():
        for el in elements:
            if state in el.ionic_radii:
                radius_diff = abs(radius - el.ionic_radii[state])
                if radius_diff < tolerance and el.symbol != target_element.symbol:
                    similar_elements.append((el.symbol, state, radius_diff))
    return sorted(similar_elements, key=lambda x: x[2])

def make_swap_table():
    elements = [Element(el) for el in Element]

    swap_table = {}

    for el in elements:
        swap_table[el.symbol] = [
            x[0] for x in find_similar_elements(el, elements)
        ]

    return swap_table

def propose_new_structures(cif_str, swap_table, max_swaps=1):
    struct = Structure.from_str(cif_str, fmt="cif")

    elements = [el.symbol for el in struct.species]
    swappable_elements = [
        el for el in elements if el in swap_table and len(swap_table[el]) > 0
    ]

    num_possible_swaps = sum([len(swap_table[el]) for el in swappable_elements])
    num_swaps = min(num_possible_swaps, max_swaps)

    relaxer = Relaxer() 
    new_bulks = []
    for _ in range(num_swaps):
        old_el = random.choice(swappable_elements)
        possible_new = swap_table[old_el]
        # new_el = random.choice(possible_new)
        new_el = possible_new[0]

        new_bulk = struct.copy()
        new_bulk.replace_species({old_el: new_el})

        relax_results = relaxer.relax(new_bulk)
        final_structure = relax_results['final_structure']
        final_relaxed_energy = relax_results['trajectory'].energies[-1]
        
        new_bulks.append(dict(
            cif=final_structure.to(fmt="cif"), 
            energy=final_relaxed_energy
        ))

    new_bulks = pd.DataFrame(new_bulks)
    return new_bulks

def main(args):
    swap_table = make_swap_table()
    # input_file = args.input_file

    input_file = "/private/home/ngruver/ocp-modeling-dev/llm/mp_training_data/val.csv"
    df = pd.read_csv(input_file)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # cif_idx = int(os.environ['SLURM_ARRAY_TASK_ID'])

    structure = None
    while structure is None or len(structure) > 10:
        idx = np.random.randint(len(df))
        k = 'cif_str' if 'cif_str' in df.columns else 'cif'
        start_crystal_cif = df[k][idx]
        structure = Structure.from_str(start_crystal_cif, fmt="cif")

        structure = Structure.from_str(start_crystal_cif, fmt="cif")
        species = list(set([str(s) for s in structure.species]))
    
        if len(species) == 1:
            continue

        if all([len(swap_table[s]) == 0 for s in species]):
            continue

    print(start_crystal_cif)

    cif_idx = idx

    output_dir = f"{args.output_dir}/{str(cif_idx)}"

    new_structs = propose_new_structures(
        df.iloc[cif_idx]['cif_str'], swap_table
    )

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_file = os.path.join(output_dir, "new_structs.csv")
    new_structs.to_csv(output_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.add_argument("--input-file", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    args = parser.parse_args()

    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    import tensorflow as tf
    tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

    main(args)