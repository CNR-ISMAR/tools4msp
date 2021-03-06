Layer expression input
======================

When managed from GAIR geoportal the modules can use as input either
layers already present inside the geoportal or different combination
of existing layers that are created by geodatabuilder tool an saved as *layer expressions*

To create a new expression first select ``geodatabuilder``
from ``data`` menu.

.. figure:: images/GAIR_menu_data.png
   :alt: Data menu of GAIR interface
   :align: center
   :name: gair-menu-data

   Menu Data on GAIR interface

On the first page available layer expressions are listed

.. figure:: images/GAIR_gdbuilder_list.png
   :alt: Geodatabuilder list of existing expressions
   :align: center
   :name: gair-gdb-list

   List of existing layer expressions

.. _create_new-gd-exp:

How to create a new expression
------------------------------

Select the ``new expression`` button from the expression list or select
``Create geodatabuilder`` entry from  ``Data`` Menu (:numref:`gair-menu-data`)

.. figure:: images/GAIR_gdbuilder_new_exp.png
   :alt: Geodatabuilder create expression interface
   :align: center
   :name: gair-gdb-create

   Create expression interface


The create expression interface contains the following items

1) Name of the layer expression yo're going to create. This name will be showed in expression list

2) Drop-down list of existing case study, select here the case study you are going to run
   (please note that both default and customized case studies are listed).

3) Description of the layer expression: a small text that describe this layer expression useful for other users

4) Expression builder: here is shown the expression components (layers, operators, numbers)
   click on one item to reorder, change value or delete them.

5) Filters to narrow the layers list

6) Layers list: just click on the layer name to add it to the current
   expression.

7) Operators: click on one of the operators to add it to the expression.

8) Save the current expression.

.. TODO remove this warning when the issue is

Set Name, Description and Case study for your expression, then select
the layers you want to use from layers list and add operators or
integer values then click on ``Save Expression``.

First of all compile Name and description for you expression (1)(3) and select case study module
in which it will be available (2).

Select the layers you'r going to use in your expression. At present time (2020-05)
you can choose this types of layer


.. warning::
   Due to technical reasons the layers list could be not complete
   when loaded for the first time: please always use the ``CLEAR`` button
   on filter mask (:numref:`gdb-filter-clear`) before set a new filter.

   .. figure:: images/GAIR_gdbuilder_filter_clear.png
      :alt: GAIR geodatabuilder filter
      :align: center
      :name: gdb-filter-clear

      GAIR geodatabuilder filter

Run case study with your expression
-----------------------------------
The layer expression you've just created will be listed after default
layers with a ``Run Expression`` control button.

.. figure:: images/GAIR_gdbuilder_exp_run.png
   :alt: Layer expression listed in case study
   :align: center
   :name: gair-gdb-exp-run

   Layer expression listed in case study


How to check or edit existing expressions
-----------------------------------------

To run a layer expression you need to have granted access to the expression object
and all the layer used by the expression.

Starting from the expression list (:numref:`gair-gdb-list`) find
the expression of your interest according to the expression title and
description.

Open the layer expression clicking on the ``view expression`` button
and the detail page will show:

.. figure:: images/GAIR_gdbuilder_exp_details.png
   :alt: Geodatabuilder detail expression interface
   :align: center
   :name: gair-gdb-detail

   Detail expression interface

The detail interface presents the expression with layers and operators(1), the layers list (2) and
the case study which the expression is linked to (3). For information about he expression you can
contact the expression owner (4) by searching the username in ``About`` > ``People`` section.

You can quickly go to the case study from the expression detail page using the ``View case study`` button.

.. figure:: images/GAIR_gdbuilder_view_case_study.png
   :alt: Direct link to case study
   :align: center
   :name: gair-gdb-viewcs

   Direct link to case study


Duplicate expression
++++++++++++++++++++

When you create a layer expression that you want to make available
with other users to properly run a default case study you will need to
replicate the same expression in more casa studies.
Follow this steps:

#. Copy the expression with layers and operator and save to a text file for reference

#. Select the ``Create new expression button``

#. Set expression name and description, please cite the source expression

#. Add layers and operators to recreate the same expression

#. Select the case stuty of your interests.

.. warning::
        | The GAIR geoportal has an integrated user management system (see the `GAIR documentation <https://www.portodimare.eu/static/docs/usage/accounts_user_profile/index.html>`_) and access to each layer expression can be granted or denied by the object's owner or GAIR administrators.

In case one or more layers used in the expression are not available
(you dont'have acces to them or they've been deleted) you'll se an error
inside the expression box:

.. figure:: images/GAIR_gdbuilder_error.png
   :alt:  Error on geodatabuilder: layer not accessible
   :align: center
   :name: gair-gdb-error

   Error on geodatabuilder: layer not accessible

Please contact the layer expression owner ( ``About`` > ``People`` section) or
the GAIR administrators.

If you are the owner of the expression you  will be able to edit or remove the expression

.. figure:: images/GAIR_gdbuilder_exp_editable.png
   :alt: Geodatabuilder editable expression interface
   :align: center
   :name: gair-gdb-edit

   Detail of editable expression interface

In :numref:`gair-gdb-edit` you can see the edit controls for ``remove expression`` (1) and ``edit expression`` (2).

Reuse the layer expression in multiple case study run
+++++++++++++++++++++++++++++++++++++++++++++++++++++

In case you need to reuse your expression in multiple case studies but you don't need to share the
expression with other users follow this path:

#. create your layer expression and link it to your first module run (e.g. Slovenia-MUC)

#. run your first case study module as described in :ref:`tutorial-muc` and :ref:`tutorial-cea`

#. edit your expression and link to next module case study you're going to run

#. open the new module case study and you'll find the layer expression among input layers






