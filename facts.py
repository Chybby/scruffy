from __future__ import print_function

import random

FACTS = [
    ('Recycling one aluminium can saves enough energy to run a TV for three'
     ' hours - or the equivalent of 2 litres of petrol.'),
    ('On average, a baby will go through 6000 disposable diapers before they'
     ' are potty trained.'),
    ('Motor oil never wears out, it just gets dirty. Old oil can be recycled,'
     ' re-refined and used again.'),
    ('Every year we make enough plastic film to shrink-wrap the state of'
     ' Texas.'),
    ('There is a nonprofit company in Japan that recycles old dentures and'
     ' donates the proceeds to UNICEF.'),
    ('During World War 1, enough metal was salvaged from corset stays to build'
     ' two warships.'),
    ('It takes 80-100 years for an aluminum can to decompose in a landfill.'),
    ('Glass takes over 1,000,000 (one million) years to decompose in a'
     ' landfill.'),
    ('Old crayons don\'t decompose but you can send your unused colors into'
     ' Crazy Crayons to have them recycled into new!'),
    ('It takes a 15-year-old tree to produce 700 grocery bags.'),
    ('Recycling aluminium cans saves 95%% of the energy used to make new'
     ' cans.'),
    ('Used condoms were recycled into hair bands in Southern China. They sold'
     ' quite well, although several physicians voiced concerns about potential'
     ' hygiene problems.'),
    ('Burying coffins also means that 90,272 tons of steel, 2,700 tons of'
     ' copper and bronze, and over 30 million feet of hard wood covered in'
     ' toxic laminates are also buried per year.'),
    ('Before the twentieth century, most Americans and Europeans practiced'
     ' habits of reuse and recycling that prevailed in agricultural'
     ' communities. For example, in the Middle Ages, tanners would often'
     ' collect urine to use in tanning animal skins or making gunpowder.'),
    ('Bones were often recycled into common household items such as buttons,'
     ' glue, and paper.'),
]


def get_bin_fact():
    return random.choice(FACTS)
