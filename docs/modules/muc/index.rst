Maritime Use Conflict
=====================

Aim of the module
-------------------

The MUS module allows to assess and map maritime use conflicts.
Conflicts (MUC) are defined as the constraints creating
disadvantages to maritime activities located in a given sea area. The
method applied is in line with COEXIST Project methodology (Gramolini
et al., 2010), already applied within the Adriatic-Ionian Sea
(Barbanti et al., 2015; Depellegrin et al., 2017).

.. figure:: images/muc_conceptual_schema.png
   :alt: MUC conceptual schema
   :align: center
   :name: muc-conceptual-schema

   Conceptual schema of the Maritime Use Conflict module

Potential synergies of maritime uses (MUS) were defined and mapped in
terms Multi-Use (MU) potentials. MU is defined as “the joint use of
resources in close geographic proximity by either a single user or
multiple users.” (Schupp et al. under review). Examples include for
instance the identification of areas adequate for tourism-driven MU,
such as pescatourism or combination of aquauculture activities and
tourism.  In addition to geospatial and statistical results, general
information on the Driver-Added Value-Barrier-Impact (DABI) of a given
MU will be provided.

Finally, the module will provide a report of existing planning
instruments (grouped by scale and type) considering the extension of
the selected area and the presence/absence of specific human uses
(governance analysis).

MUSC is based on a case-study driven approach. A case-study is defined
as pre-configured set of specific data with consistent spatial and
temporal coverage of environmental and anthropogenic uses,
incorporating all the necessary parameter for the module run.  The
synergy expressed through Multi-Use potentials will be analyzed
according to ongoing and past projects and through the analysis of EU
and macro-regional strategies and national strategies (Blue MED SRIA;
EUSAIR, etc…)


Module inputs
-------------

Input layers
++++++++++++

.. figure:: images/muc_input_layers.png
   :alt: MUC imput layer
   :align: center
   :name: muc-input-layers

   Web map representing the geospatial distribution of human activities.



COEXISTS rules and human traits
+++++++++++++++++++++++++++++++

MUC methodology is implemented according to Barbanti et al. 2015. The following operational steps allow to define
the potential conflict score for pariwise combination:

1. human uses classification and assignment of numerical values to five traits (mobility, spatial, vertical and temporal scale, location) (ses :numref:`muc-factors`;
2. assignment of the three rules to calculate default level of conflict for pairwise combinations
3. expert-based adjustments to define the validate version of the potential conflict score matrix (see :numref:`muc-potential-score-matrix`)

According to original COEXIST methodology, the rules for automatically calculate the default level of conflict are:

- Rule 1: if vertical domain of activity 1 is different from vertical domain of activity 2 and no one of them
  interests the whole water column then conflict score is equal to 0;
- Rule 2: If both activities are “mobile” then conflict score is equal to the minimum of temporal domain plus the
  minimum of spatial domain
- Rule 3: if Rule1 and Rule2 cannot be applied then the conflict score is equal to the maximum value of temporal
  domain plus the maximum value of spatial domain.


.. table:: Potential conflict traits for classifing human uses.
   :widths: auto
   :name: muc-factors

   +---+-------------------------+-------------------------+--------------+
   |   |  Human traits           |  Value                  |  Value       |
   +===+=========================+=========================+==============+
   | 1 | Vertical scale          | - Pelagic               | - Value = 1  |
   |   |                         | - Benthic               | - Value = 2  |
   |   |                         | - whole water column    | - Value = 3  |
   +---+-------------------------+-------------------------+--------------+
   | 2 | Spatial  scale          | - Small                 | - Value = 1  |
   |   |                         | - Medium                | - Value = 2  |
   |   |                         | - Large                 | - Value = 3  |
   +---+-------------------------+-------------------------+--------------+
   | 3 | Temporal scale          | - Small                 | - Value = 1  |
   |   |                         | - Medium                | - Value = 2  |
   |   |                         | - Large                 | - Value = 3  |
   +---+-------------------------+-------------------------+--------------+
   | 4 | Mobility                | - Mobile                | - Value = 1  |
   |   |                         | - Fixed                 | - Value = 2  |
   +---+-------------------------+-------------------------+--------------+
   | 5 | Location                | - Land                  | - Value = 1  |
   |   |                         | - Sea                   | - Value = 2  |
   +---+-------------------------+-------------------------+--------------+


.. figure:: images/muc_potential_score_matrix.png
   :alt: MUC potential score matrix
   :align: center
   :name: muc-potential-score-matrix

   Example of potential conflict score matrix


Module outputs
--------------


References
----------

Depellegrin, Daniel, Stefano Menegon, Giulio Farella, Michol Ghezzo, Elena Gissi, Alessandro Sarretta, Chiara Venier,
and Andrea Barbanti. 2017. “Multi-Objective Spatial Tools to Inform Maritime Spatial Planning in the Adriatic Sea.”
Science of The Total Environment 609 (December): 1627–39. https://doi.org/10.1016/j.scitotenv.2017.07.264.

Menegon, Stefano, Daniel Depellegrin, Giulio Farella, Alessandro Sarretta, Chiara Venier, and Andrea Barbanti. 2018.
“Addressing Cumulative Effects, Maritime Conflicts and Ecosystem Services Threats through MSP-Oriented Geospatial
Webtools.” Ocean & Coastal Management 163 (September): 417–36. https://doi.org/10.1016/j.ocecoaman.2018.07.009.

Menegon, Stefano, Alessandro Sarretta, Daniel Depellegrin, Giulio Farella, Chiara Venier, and Andrea Barbanti. 2018.
“Tools4MSP: An Open Source Software Package to Support Maritime Spatial Planning.” PeerJ Computer Science 4 (October):
e165. https://doi.org/10.7717/peerj-cs.165.
