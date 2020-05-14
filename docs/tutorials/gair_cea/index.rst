..  _tutorial-cea:

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

   CEA case study detail page

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

To check the content of a layer you can click on the layer thumbnail to open a new window
with a larger preview image and a ``Download layer`` control.

.. figure:: images/CEA_case_study_layer.png
   :alt: CEA case study detail page
   :align: center
   :name: cea-cs-layerpreview

   CEA case study layer preview

.. _default-cea-case-studies:

Configure default run
---------------------

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




    You can quickly select all layers using ``select all layers`` checkbox, this will compute CEA
    considering all enviromental components and all human uses available-
    If you need to investigate the cumulative effects on a subset of components or human uses you can manually
    select (or deselect) the layers to consider.


#.  Review or change input values for weights/sensitivities matrix.
    Click on ``SET MATRIX INPUTS`` to open the matrix input widget for weights and sensitivities

    .. figure:: images/CEA_matrix_weights.png
      :alt: CEA weights matrix input widget
      :align: center
      :name: cea-cs-weightmatrix

      CEA weights matrix input widget

    .. figure:: images/CEA_matrix_weights.png
       :alt: CEA sensitivities matrix input widget
       :align: center
       :name: cea-cs-sensmatrix

       CEA sensitivities matrix input widget

#.  Click on ``Run Case Study`` to run teh module for the current case study.
    When the Run is complete the results will be listed in the same page on a new tab.


    .. figure:: images/CEA_matrix_weights.png
       :alt: CEA sensitivities matrix input widget
       :align: center
       :name: cea-cs-results

       CEA results list: json results (1) and raster outpus (2)

    To make another Run click again on the ``Layer`` tab (3).



.. _customized-cea-case-studies:

Clone case study to a customized one
------------------------------------

#. select ``Clone case Study``: the new  case study will open in the same page but
   you'll see *Type: customized*  in the summary box over 6 (:numref:`ca-cs-detail`)

#. write down the Case Study ID number in the las part of the new URL
   (e.g.  ``https://www.portodimare.eu/casestudies/XXX/``)

.. TODO remove this step when will be available case study editing

#. create new layer expression and add it to case study as described in :ref:`create_new-gd-exp`
   section and link to the new created case study (you can identify the correct
   one with title and ID see :ref:`gair-gdb-create` number 2).

#. to add new layers already stored in the geoportal you need to create a
   simple layer expression with just one layer without operators.

#. get back to the customized case study using ``View case study`` Button (:numref:`gair-gdb-viewcs`)

#. click ``Run Expression`` (:numref:`gair-gdb-exp-run`) for each customized layer

* Select layers and set matrix inputs as described in :ref:`default-cea-case-studies` section


