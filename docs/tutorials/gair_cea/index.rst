CEA Module on GAIR
==================

From ``Case studies`` select the ``Module CEA`` menu item to explore
the list of available case studies for that module.

.. figure:: ../images/GAIR_case_studies_menu.png
   :alt: GAIR case studies menu
   :align: center
   :name: gair-cs-menu

   GAIR case studies menu.

.. figure:: images/CEA_case_studies_list.png
   :alt: CEA case studies list
   :align: center
   :name: ca-cs-list

   CEA case studies list.

Each list item for CEA related case studies present a small overview of the domain area,
the case study type (default or customized), resolution of the grid, Case study title and description.

.. figure:: images/CEA_case_study_list_item.png
   :alt: CEA case study list item
   :align: center
   :name: ca-cs-list-item

   CEA case study list item.

To open a case study click on the title or "open" button. The detail page
presents all layers and layer expressions already configured for the case study

.. figure:: images/CEA_case_study_detail.png
   :alt: CEA case study detail page
   :align: center
   :name: ca-cs-detail

   CEA case study detail page.png

In the case study detail page (:numref:`ca-cs-detail`) are
presented the following elements:

1) a map section with the domain area boundaries;

2) name and description of the case study;

3) the list of input layers as described in :ref:`cea-module-inputs`;

4) the ``SET MATRIX INPUTS`` button to change values of *weights*
and *sensitivity* matrix as described in ::ref:`cea-module-inputs`;

5) the ``run case study`` button to run the CEA module within this case study;

6) the ``clone case study`` button (6) to create a
customized case study starting from this configuration;

You can either set configuration data in the default case study (input layers and input matrix)
or clone the current case study to create a customized one

Configure default run
---------------------
(in progress)

#. Select input layers layers from list.
    You'll see the list of input layers displayed as a grid with layer name,
    thumbnail and selection control.
    The input layers thumbnails are is loaded directly from the
    `API server <https://api.tools4msp.eu>`_
    and in case the thumbnails are not showed as usual could be
    due to a connection trouble with the external server.

    Please check the layers list and identify what
    kind of input each layers refers to.

    .. table:: Example of CEA input layers
       :widths: auto
       :name: gair-cea-layers

       +---------------------------------------------+---------------------------+
       | Layer                                       | Input type                |
       +=============================================+===========================+
       | Domain area boundary                        | Embedded in case study def|
       +---------------------------------------------+---------------------------+
       | Grid of analysis                            | Resolution (required)     |
       +---------------------------------------------+---------------------------+
       | Mammals                                     | environmental component   |
       +---------------------------------------------+---------------------------+
       | Fishing ports                               | human use                 |
       +---------------------------------------------+---------------------------+


    You can quickly select


#. Review or change input  for weights/sensitivities matrix.
    Click on  open the matrix input widget by

Clone case study to a customized one
------------------------------------
(in progress)
* create new layer expression and add it to case study

* add new layers to case study

