from __future__ import print_function
from math import copysign
import json
import os
import csv
import numpy as np
import pandas as pd

ALIASES = {'chloride': 'hydrochloric acid',
           'dodecylsulfonic acid': 'laurylsulfonic acid'
           }

NIGHTINGALE_FILES = {'silver': 'silver',
                     'calcium': 'calcium',
                     'hydrochloric acid': 'hydrochloric_acid',
                     'potassium': 'potassium',
                     'lithium': 'lithium',
                     'magnesium': 'magnesium',
                     'sodium': 'sodium',
                     'perchlorate acid': 'perchlorate_acid',
                     'rubidium': 'rubidium_cesium',
                     'sulfuric acid': 'sulfuric_acid',
                     'cesium': 'rubidium_cesium'
                     }


class DataCreator(object):

    data = None

    def __init__(self):
        self.load_steep()
        self.load_spresso()
        self.load_nightingale()
        self.create()
        self.patch()
        self.check()
        # self.write

    def load_spresso(self):
        z = pd.read_csv(os.path.join(os.path.dirname(__file__),
                                     'data', 'Z.csv'),
                        engine='python').columns.tolist()
        name = pd.read_csv(os.path.join(os.path.dirname(__file__),
                                        'data', 'name.csv'),
                           engine='python', sep='~', header=None,
                           names=['name'])
        pKa = pd.read_csv(os.path.join(os.path.dirname(__file__),
                                       'data', 'pKa.csv'),
                          engine='python', header=None,
                          names=['pKa {}'.format(i) for i in z])
        mobility = pd.read_csv(os.path.join(os.path.dirname(__file__),
                                            'data', 'mobility.csv'),
                               engine='python', header=None,
                               names=['mobility {}'.format(i) for i in z])
        self.spresso = pd.concat([name, pKa, mobility], axis=1)

    def load_nightingale(self):
        self.nightingale_fits = nightingale_fits = dict()

        for ion in NIGHTINGALE_FILES.keys():
            fullpath = os.path.join(os.path.dirname(__file__),
                                    'data', 'nightingale',
                                    '{}.txt'.format(NIGHTINGALE_FILES[ion]))
            data = pd.read_csv(fullpath, engine='python', header=0,
                               index_col=0, names=['value'])

            nightingale_fits[ion] = {'fit': np.polyfit(data.index,
                                                       data['value'],
                                                       deg=8
                                                       ).tolist(),
                                     'min': min(data.index),
                                     'max': max(data.index)
                                     }

    def load_steep(self):
        fullpath = os.path.join(os.path.dirname(__file__),
                                'data',
                                'STEEP_Database.csv')
        self.steep = pd.read_csv(fullpath)

    def create(self):
        self.data = dict()
        for idx, row in self.spresso.iterrows():
            name = row['name']
            entry = self.data[name.lower()] = {'name': name.lower(),
                                               '__ion__': 'Ion',
                                               }

            # check to see if the ion is in the steep database.
            """Set steep parameters"""
            steep = self.steep[self.steep['Name'].str.lower() == name.lower()]
            if not steep.empty:
                entry['enthalpy'] = [steep[loc].tolist()[0] for loc in
                                     ['deltaH', 'deltaH.1', 'deltaH.2']
                                     if not np.isnan(steep[loc].tolist()[0])]
                entry['heat_capacity'] = ([steep[loc].tolist()[0] for loc in
                                           ['deltaCp', 'deltaCp.1',
                                            'deltaCp.2']
                                           if not
                                           np.isnan(steep[loc].tolist()[0])] or
                                          None)
                entry['molecular_weight'] = steep['MW'].tolist()[0]
            else:
                entry['heat_capacity'] = None
                entry['enthalpy'] = None
                entry['molecular_weight'] = None
            #
            """Get pKa lists"""
            entry['valence'] = []
            entry['reference_pKa'] = []
            entry['reference_mobility'] = []

            for valence in [-3, -2, -1, 1, 2, 3]:
                if not np.isnan(row['pKa {}'.format(valence)]):
                    assert not np.isnan(row['mobility {}'.format(valence)]), \
                        '{} pKa must have a matching valence'.format(row[
                                                                         'name'
                                                                         ]
                                                                     )
                    entry['valence'].append(valence)
                    entry['reference_pKa'].append(row['pKa {}'.format(valence)])
                    mob = (row['mobility {}'.format(valence)] *
                           1e-9 *
                           copysign(1, valence))
                    entry['reference_mobility'].append(mob)

            if entry['heat_capacity'] and \
                    len(entry['heat_capacity']) < len(entry['valence']):
                entry['heat_capacity'].append(0)
            if entry['enthalpy'] and \
                    len(entry['enthalpy']) < len(entry['valence']):
                entry['enthalpy'].append(0)

            entry['nightingale_data'] = \
                self.nightingale_fits.get(name.lower(), None)

    def patch(self):
        self.data['taps']['heat_capacity'] = [15.0]

        # boric acid is uniquely in the STEEP database,
        # but not the Spresso database add manually.
        boric = self.steep[self.steep['Name'].str.lower() == 'boric acid']
        self.data['boric acid'] = {'name': 'boric acid',
                                   '__ion__': 'Ion',
                                   'valence': [-1],
                                   'reference_pKa': boric['pKa'].tolist(),
                                   'reference_mobility':
                                   [boric['Mobility'].tolist()[0]*-1],
                                   'enthalpy': boric['deltaH'].tolist(),
                                   'heat_capacity': boric['deltaCp'].tolist(),
                                   'nightingale_data': None}

        # Remove valences to fix ion search
        self.data['uranyl'] = self.data.pop('uranyl(vi)')
        self.data['iron'] = self.data.pop('iron(ii)')

    def create_aliases(self):
        pass

    def write(self):
        path = os.path.join(os.path.dirname(__file__), '..',
                            'ionize', 'Database', 'ion_data.json')
        with open(path, 'wb') as ion_file:
            json.dump(self.data, ion_file,
                      sort_keys=True, indent=4, separators=(',', ': '))

    def check(self):
        # Check to make that all of the entries in the steep db were added
        # for name in steep_db.keys():
        #     if name not in steep_common:
        #         print(name, 'in Steep database not added')

        print(len(self.data), 'ions in database')
        # print(n_steep, 'ions from steep')


if __name__ == '__main__':
    creator = DataCreator()