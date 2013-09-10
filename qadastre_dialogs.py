# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Qadastre - Dialog classes
                                                                 A QGIS plugin
 This plugins helps users to import the french land registry ('cadastre')
 into a database. It is meant to ease the use of the data in QGIs
 by providing search tools and appropriate layer symbology.
                                                            -------------------
                begin                                : 2013-06-11
                copyright                        : (C) 2013 by 3liz
                email                                : info@3liz.com
 ***************************************************************************/

/***************************************************************************
 *                                                                                                                                                 *
 *     This program is free software; you can redistribute it and/or modify    *
 *     it under the terms of the GNU General Public License as published by    *
 *     the Free Software Foundation; either version 2 of the License, or         *
 *     (at your option) any later version.                                                                     *
 *                                                                                                                                                 *
 ***************************************************************************/
"""

import csv
import os.path
import operator
import re
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import QgsGenericProjectionSelector

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/forms")

from db_manager.db_plugins.plugin import DBPlugin, Schema, Table
from db_manager.db_plugins import createDbPlugin

# --------------------------------------------------------
#        import - Import data from EDIGEO and MAJIC files
# --------------------------------------------------------


class qadastre_common():

    def __init__(self, dialog):

        self.dialog = dialog

        # plugin directory path
        self.plugin_dir = QFileInfo(QgsApplication.qgisUserDbFilePath()).path() + "/python/plugins/Qadastre"

        # default auth id for layers
        self.defaultAuthId = 'EPSG:2154'


    def updateLog(self, msg):
        '''
        Update the log
        '''
        self.dialog.txtLog.append(msg)


    def updateProgressBar(self):
        '''
        Update the progress bar
        '''
        if self.dialog.go:
            self.dialog.step+=1
            self.dialog.pbProcess.setValue(int(self.dialog.step * 100/self.dialog.totalSteps))


    def updateConnectionList(self):
        '''
        Update the combo box containing the database connection list
        '''
        QApplication.setOverrideCursor(Qt.WaitCursor)

        dbType = unicode(self.dialog.liDbType.currentText()).lower()
        self.dialog.liDbConnection.clear()

        if self.dialog.liDbType.currentIndex() != 0:
            self.dialog.dbType = dbType
            # instance of db_manager plugin class
            dbpluginclass = createDbPlugin( dbType )
            self.dialog.dbpluginclass = dbpluginclass

            # fill the connections combobox
            for c in dbpluginclass.connections():
                self.dialog.liDbConnection.addItem( unicode(c.connectionName()))
        QApplication.restoreOverrideCursor()

    def toggleSchemaList(self, t):
        '''
        Toggle Schema list and inputs
        '''
        self.dialog.liDbSchema.setEnabled(t)
        if hasattr(self.dialog, "inDbCreateSchema"):
            self.dialog.inDbCreateSchema.setEnabled(t)
            self.dialog.btDbCreateSchema.setEnabled(t)


    def updateSchemaList(self):
        '''
        Update the combo box containing the schema list if relevant
        '''
        self.dialog.liDbSchema.clear()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        connectionName = unicode(self.dialog.liDbConnection.currentText())
        self.dialog.connectionName = connectionName
        dbType = unicode(self.dialog.liDbType.currentText()).lower()

        # Deactivate schema fields
        self.toggleSchemaList(False)

        if dbType == 'postgis':

            # Activate schema fields
            self.toggleSchemaList(True)

            # Get schema list
            dbpluginclass = createDbPlugin( dbType, connectionName )
            self.dialog.dbpluginclass = dbpluginclass
            connection = dbpluginclass.connect()
            if connection:
                self.dialog.connection = connection
                db = dbpluginclass.database()
                if db:
                    self.dialog.db = db
                    self.dialog.schemaList = []
                    for s in db.schemas():
                        self.dialog.liDbSchema.addItem( unicode(s.name))
                        self.dialog.schemaList.append(unicode(s.name))
        QApplication.restoreOverrideCursor()


    def checkDatabaseForExistingStructure(self):
        '''
        Search among a database / schema
        if there are alreaday Cadastre data
        in it
        '''
        hasData = False
        searchTable = u'geo_commune'
        if self.dialog.db:
            schemaSearch = [s for s in self.dialog.db.schemas() if s.name == self.dialog.schema]
            schemaInst = schemaSearch[0]
            getSearchTable = [a for a in self.dialog.db.tables(schemaInst) if a.name == searchTable]
            if getSearchTable:
                hasData = True

        self.dialog.dbHasData = hasData


    def getLayerFromLegendByTableName(self, tablename):
        '''
        Get the layer from QGIS legend
        corresponding to a database
        table name (postgis or sqlite)
        '''

        layer = None
        layers = self.dialog.iface.legendInterface().layers()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                if layer.providerType() in (u'postgres', u'spatialite'):
                    uri = layer.dataProvider().dataSourceUri()
                    if '"%s"' % tablename in uri:
                        return layer





from qadastre_import_form import *
from qadastre_import import *

class qadastre_import_dialog(QDialog, Ui_qadastre_import_form):
    def __init__(self, iface):
        QDialog.__init__(self)
        self.iface = iface
        self.setupUi(self)

        # common qadastre methods
        self.qc = qadastre_common(self)

        # Signals/Slot Connections
        self.liDbType.currentIndexChanged[str].connect(self.qc.updateConnectionList)
        self.liDbConnection.currentIndexChanged[str].connect(self.qc.updateSchemaList)
        self.btDbCreateSchema.clicked.connect(self.createSchema)
        self.btProcessImport.clicked.connect(self.processImport)

        # path buttons selectors
        from functools import partial
        self.pathSelectors = {
            "edigeoSourceDir" : {
                "button" : self.btEdigeoSourceDir,
                "input" : self.inEdigeoSourceDir
            },
            "majicSourceDir" : {
                "button" : self.btMajicSourceDir,
                "input" : self.inMajicSourceDir
            }
        }
        for key, item in self.pathSelectors.items():
            control = item['button']
            slot = partial(self.chooseDataPath, key)
            control.clicked.connect(slot)

        # projection selector
        self.projSelectors = {
            "edigeoSourceProj" : {
                "button" : self.btEdigeoSourceProj,
                "input" : self.inEdigeoSourceProj,
                "sentence" : "Choisir la projection des fichiers Edigeo"
            },
            "edigeoTargetProj" : {
                "button" : self.btEdigeoTargetProj,
                "input" : self.inEdigeoTargetProj,
                "sentence" : "Choisir la projection de destination"
            }
        }
        for key, item in self.projSelectors.items():
            control = item['button']
            slot = partial(self.chooseProjection, key)
            control.clicked.connect(slot)

        # Set initial values
        self.dataVersionList = [ '2011', '2012']
        self.dbType = None
        self.dbpluginclass = None
        self.connectionName = None
        self.connection = None
        self.db = None
        self.schema = None
        self.schemaList = None
        self.dbHasData = None
        self.edigeoSourceProj = None
        self.edigeoTargetProj = None
        self.edigeoDepartement = None
        self.edigeoDirection = None
        self.edigeoLot = None

        self.qadastreImportOptions = {
            'dataVersion' : '2012',
            'dataYear' : '2011',
            'edigeoSourceDir' : None,
            'edigeoSourceProj' : None,
            'edigeoTargetProj' : None,
            'majicSourceDir' : None
        }

        self.majicSourceFileNames = [
            {'key': '[FICHIER_BATI]', 'value': 'REVBATI.800'},
            {'key': '[FICHIER_FANTOIR]', 'value': 'TOPFANR.800'},
            {'key': '[FICHIER_LOTLOCAL]', 'value': 'REVD166.800'},
            {'key': '[FICHIER_NBATI]', 'value': 'REVNBAT.800'},
            {'key': '[FICHIER_PDL]', 'value': 'REVFPDL.800'},
            {'key': '[FICHIER_PROP]', 'value': 'REVPROP.800'}
        ]

    def populateDataVersionCombobox(self):
        '''
        Populate the list of data version (representing a year)
        '''
        self.liDataVersion.clear()
        for year in self.dataVersionList:
            self.liDataVersion.addItem(year)




    def createSchema(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if self.db == None:
                QMessageBox.information(
                    self,
                    QApplication.translate("DBManagerPlugin", "Sorry"),
                    QApplication.translate("DBManagerPlugin", "No database selected or you are not connected to it.")
                )
                return
            schema = self.inDbCreateSchema.text()
        finally:
            QApplication.restoreOverrideCursor()

        if schema:
            try:
                self.db.createSchema(schema)

            except BaseError as e:

                DlgDbError.showError(e, self)
                self.qc.updateLog(e.msg)
                return

            finally:
                self.qc.updateSchemaList()
                listDic = { self.schemaList[i]:i for i in range(0, len(self.schemaList)) }
                self.liDbSchema.setCurrentIndex(listDic[schema])
                self.inDbCreateSchema.clear()
                QApplication.restoreOverrideCursor()


    def chooseDataPath(self, key):
        '''
        Ask the user to select a folder
        and write down the path to appropriate field
        '''
        ipath = QFileDialog.getExistingDirectory(
            None,
            "Choisir le répertoire contenant les fichiers",
            str(self.pathSelectors[key]['input'].text().encode('utf-8')).strip(' \t')
        )
        if os.path.exists(unicode(ipath)):
            self.pathSelectors[key]['input'].setText(unicode(ipath))

    def chooseProjection(self, key):
        '''
        Let the user choose a SCR
        '''
        header = u"Choisir la projection"
        sentence = self.projSelectors[key]['sentence']
        projSelector = QgsGenericProjectionSelector(self)
        projSelector.setMessage( "<h2>%s</h2>%s" % (header.encode('UTF8'), sentence.encode('UTF8')) )
        projSelector.setSelectedAuthId(self.qc.defaultAuthId)
        if projSelector.exec_():
            self.crs = QgsCoordinateReferenceSystem( projSelector.selectedCrsId(), QgsCoordinateReferenceSystem.InternalCrsId )
            if len(projSelector.selectedAuthId()) == 0:
                QMessageBox.information(
                    self,
                    self.tr("Qadastre"),
                    self.tr(u"Aucun système de coordonnée de référence valide n'a été sélectionné")
                )
                return
            else:
                self.projSelectors[key]['input'].clear()
                self.projSelectors[key]['input'].setText(self.crs.authid() + " - " + self.crs.description())
        else:
            return



    def processImport(self):
        '''
        Lancement du processus d'import
        '''
        if not self.db:
            msg = u'Veuillez sélectionner une base de données'
            QMessageBox.critical(self, self.tr("Qadatre"), self.tr(msg))
            return None

        self.dataVersion = unicode(self.liDataVersion.currentText())
        self.dataYear = unicode(self.inDataYear.text())
        self.schema = unicode(self.liDbSchema.currentText())
        self.majicSourceDir = str(self.inMajicSourceDir.text().encode('utf-8')).strip(' \t')
        self.edigeoSourceDir = str(self.inEdigeoSourceDir.text().encode('utf-8')).strip(' \t')
        self.edigeoDepartement = unicode(self.inEdigeoDepartement.text())
        self.edigeoDirection = unicode(self.inEdigeoDirection.text())
        self.edigeoLot = unicode(self.inEdigeoLot.text())
        self.edigeoSourceProj = unicode(self.inEdigeoSourceProj.text().split( " - " )[ 0 ])
        self.edigeoTargetProj = unicode(self.inEdigeoTargetProj.text().split( " - " )[ 0 ])

        # qadastreImport instance
        qi = qadastreImport(self)

        # Check if structure already exists in the database/schema
        self.qc.checkDatabaseForExistingStructure()

        #~ # Run Script for creating tables
        if not self.dbHasData:
            qi.installOpencadastreStructure()

        # Run MAJIC import
        if os.path.exists(self.majicSourceDir):
            qi.importMajic()

        # Run Edigeo import
        if os.path.exists(self.edigeoSourceDir):
            qi.importEdigeo()

        qi.endImport()

# --------------------------------------------------------
#        load - Load data from database
# --------------------------------------------------------

from qadastre_load_form import *

class qadastre_load_dialog(QDockWidget, Ui_qadastre_load_form):
    def __init__(self, iface):
        QDockWidget.__init__(self)
        self.iface = iface
        self.setupUi(self)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self)

        # common qadastre methods
        self.qc = qadastre_common(self)

        # default style to apply for Qadastre layers
        self.themeDir = unicode(self.liTheme.currentText())
        if not os.path.exists(os.path.join(
            self.qc.plugin_dir,
            "styles/%s" % self.themeDir
        )):
            self.themeDir = 'classique'
        # set Qadastre SVG path if not set
        qadastreSvgPath = os.path.join(
            self.qc.plugin_dir,
            "styles/%s/svg" % self.themeDir
        )
        s = QSettings()
        qgisSvgPaths = s.value("svg/searchPathsForSVG", 10, type=str)
        if not qadastreSvgPath in qgisSvgPaths:
            s.setValue("svg/searchPathsForSVG", qadastreSvgPath)
            self.qc.updateLog(u"* Le chemin contenant les SVG du plugin Qadastre a été ajouté dans les options de QGIS")

        # Signals/Slot Connections
        self.liDbType.currentIndexChanged[str].connect(self.qc.updateConnectionList)
        self.liDbConnection.currentIndexChanged[str].connect(self.qc.updateSchemaList)
        self.btProcessLoading.clicked.connect(self.processLoading)

        # Set initial values
        self.go = True
        self.step = 0
        self.totalSteps = 0
        self.dbType = None
        self.dbpluginclass = None
        self.connectionName = None
        self.connection = None
        self.db = None
        self.schema = None
        self.schemaList = None
        self.dbHasData = None

        self.qgisQadastreLayerList = [
            {'name': 'geo_commune', 'table': 'geo_commune', 'geom': 'geom'},
            {'name': 'geo_zoncommuni', 'table': 'geo_zoncommuni'},
            {'name': 'geo_label_zoncommuni', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'ZONCOMMUNI_id\''},
            {'name': 'geo_subdsect', 'table': 'geo_subdsect', 'geom': 'geom'},
            {'name': 'geo_subdfisc', 'table': 'geo_subdfisc', 'geom': 'geom'},
            {'name': 'geo_label_subdfisc', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'SUBDFISC_id\''},
            {'name': 'geo_batiment', 'table': 'geo_batiment', 'geom': 'geom'},
            {'name': 'geo_parcelle', 'table': 'geo_parcelle', 'geom': 'geom'},
            {'name': 'geo_label_parcelle', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'PARCELLE_id\''},
            {'name': 'geo_lieudit', 'table': 'geo_lieudit', 'geom': 'geom'},
            {'name': 'geo_label_lieudit', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'LIEUDIT_id\''},
            {'name': 'geo_section', 'table': 'geo_section', 'geom': 'geom'},
            {'name': 'geo_label_section', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'SECTION_id\''},
            {'name': 'geo_borne', 'table': 'geo_borne', 'geom': 'geom'},
            {'name': 'geo_croix', 'table': 'geo_croix'},
            {'name': 'geo_ptcanv', 'table': 'geo_ptcanv', 'geom': 'geom'},
            {'name': 'geo_symblim', 'table': 'geo_symblim', 'geom': 'geom'},
            {'name': 'geo_tronfluv', 'table': 'geo_tronfluv', 'geom': 'geom'},
            {'name': 'geo_label_tronfluv', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'TRONFLUV_id\''},
            {'name': 'geo_tsurf', 'table': 'geo_tsurf', 'geom': 'geom'},
            {'name': 'geo_label_tsurf', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'TSURF_id\''},
            {'name': 'geo_tpoint', 'table': 'geo_tpoint', 'geom': 'geom'},
            {'name': 'geo_label_tpoint', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'TPOINT_id\''},
            {'name': 'geo_tline', 'table': 'geo_tline', 'geom': 'geom'},
            {'name': 'geo_label_tline', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'TLINE_id\''},
            {'name': 'geo_label_num_voie', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'NUMVOIE_id\''},
            {'name': 'geo_label_voiep', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'VOIEP_id\''},
            {'name': 'geo_parcelle_uf', 'table': 'geo_parcelle', 'geom':'geom_uf'},
            {'name': 'geo_label_parcelle_uf', 'table': 'geo_label', 'geom': 'geom', 'sql': '"ogr_obj_lnk_layer" = \'PARCELLE_id\''}
        ]


    def processLoading(self):

        # Get selected options
        providerName = self.dbpluginclass.providerName()
        qgisQadastreLayers = []
        communeLayer = None
        self.schema = unicode(self.liDbSchema.currentText())
        self.totalSteps = len(self.qgisQadastreLayerList)

        # Run the loading
        if self.connection:
            if self.db:
                # Get database list of tables
                layerUri = self.db.uri()
                schemaSearch = [s for s in self.db.schemas() if s.name == self.schema]
                schemaInst = schemaSearch[0]
                dbTables = self.db.tables(schemaInst)

                # Get status of override combobox
                override = unicode(self.liOverrideLayer.currentText())

                # Loop throuhg qgisQastreLayerList and load each corresponding table
                for item in self.qgisQadastreLayerList:

                    # update progress bar
                    self.qc.updateLog(u'* Table %s' % item['name'])
                    self.step+=1
                    self.qc.updateProgressBar()

                    # Get db_manager table instance
                    table = [a for a in dbTables if a.name == item['table']][0]
                    sql = ""
                    if item.has_key('sql'):
                        sql = item['sql']
                    geomCol = ""
                    if item.has_key('geom'):
                        geomCol = item['geom']

                    # Check if the layer is already in QGIS
                    load = True
                    cLayer = self.qc.getLayerFromLegendByTableName(item['table'])
                    if cLayer:
                        if override == 'Remplacer':
                            self.qc.updateLog(u'  - Remplacement de la couche %s' % item['name'])

                        else:
                            self.qc.updateLog(u'  - La couche %s a été conservée' % item['name'])
                            load = False

                    # Create vector layer
                    if table and load:
                        tableName = table.name
                        uniqueCol = table.getValidQGisUniqueFields(True) if table.isView else None
                        layerUri.setDataSource(
                            self.schema,
                            tableName,
                            geomCol,
                            sql,
                            uniqueCol.name if uniqueCol else ""
                        )
                        vlayer = QgsVectorLayer(layerUri.uri(), item['name'], providerName)

                        # apply style
                        qmlPath = os.path.join(
                            self.qc.plugin_dir,
                            "styles/%s/%s.qml" % (self.themeDir, item['name'])
                        )
                        if os.path.exists(qmlPath):
                            vlayer.loadNamedStyle(qmlPath)

                        # append vector layer to the list
                        qgisQadastreLayers.append(vlayer)

                        # keep commune layer to later zoom to extent
                        if item['name'] == 'geo_commune':
                            communeLayer = vlayer


                # Add layer to QGIS registry
                QgsMapLayerRegistry.instance().addMapLayers(qgisQadastreLayers)

                # Zoom to layer commune
                if communeLayer:
                    self.iface.setActiveLayer(communeLayer)
                    activeLayer = self.iface.activeLayer()
                    if activeLayer:
                        self.iface.zoomToActiveLayer()

                # progress bar
                self.qc.updateLog(u'Chargement des couches dans QGIS')
                self.step+=1
                self.qc.updateProgressBar()

                # Final message
                QMessageBox.information(
                    self,
                    self.tr("Qadastre"),
                    self.tr(u"Les données ont bien été chargées dans QGIS")
                )
                self.pbProcess.setValue(0)




# --------------------------------------------------------
#        search - search for data among database
# --------------------------------------------------------

from qadastre_search_form import *

class qadastre_search_dialog(QDockWidget, Ui_qadastre_search_form):
    def __init__(self, iface):
        QDockWidget.__init__(self)
        self.iface = iface
        self.setupUi(self)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self)

        # common qadastre methods
        self.qc = qadastre_common(self)

        self.mc = self.iface.mapCanvas()
        self.communeLayer = None
        self.communeFeatures = None
        self.communeRequest = None
        self.selectedCommuneFeature = None
        self.sectionLayer = None
        self.sectionFeatures = None
        self.sectionRequest = None
        self.sectionCommuneFeature = None


        self.searchComboBoxes = {
            'commune': {
                'widget': self.liCommune,
                'labelAttribute': 'tex2',
                'valueAttribute': 'tex2',
                'table': 'geo_commune',
                'layer': None,
                'request': None,
                'attributes': ['tex2','idu','geom'],
                'features': None,
                'chosenFeature': None
            },
            'section': {
                'widget': self.liSection,
                'labelAttribute': 'idu',
                'valueAttribute': 'idu',
                'table': 'geo_section',
                'layer': None,
                'request': None,
                'attributes': ['tex','idu','geom'],
                'features': None,
                'chosenFeature': None
            }
        }

        # setup some gui items
        self.setupCommuneCombobox()
        self.setupSectionCombobox()

        # signals/slots
        self.visibilityChanged.connect(self.onVisibilityChange)

        # commune combobox
        self.liCommune.editTextChanged[str].connect(self.onCommuneUpdate)
        # section combobox
        self.liSection.editTextChanged[str].connect(self.onSectionUpdate)
        # place action buttons
        self.btZoomerLieu.clicked.connect(self.setZoomToChosenPlace)
        self.btCentrerLieu.clicked.connect(self.setCenterToChosenPlace)
        self.btSelectionnerLieu.clicked.connect(self.setSelectionToChosenPlace)


    def setupSearchCombobox(self, combo, filterExpression=None):
        '''
        Create and fill a line edit with town list
        And add autiocompletion
        '''

        # Get widget
        searchCombo = self.searchComboBoxes[combo]
        cb = searchCombo['widget']
        cb.clear()
        cb.addItem('', '')

        # Get corresponding QGIS layer
        itemList = []
        layer = self.qc.getLayerFromLegendByTableName(searchCombo['table'])
        self.searchComboBoxes[combo]['layer'] = layer
        if layer:

            # Get all features
            keepattributes = self.searchComboBoxes[combo]['attributes']
            request = QgsFeatureRequest().setSubsetOfAttributes(
                keepattributes,
                layer.pendingFields()
            )

            self.searchComboBoxes[combo]['request'] = request
            features = layer.getFeatures(request)
            self.searchComboBoxes[combo]['features'] = features
            labelAttribute = self.searchComboBoxes[combo]['labelAttribute']
            valueAttribute = self.searchComboBoxes[combo]['valueAttribute']

            # setup optionnal filter
            qe = None
            if filterExpression:
                qe = QgsExpression(filterExpression)
            for feat in features:
                keep = True
                if qe:
                    if not qe.evaluate(feat):
                        keep = False
                if keep:
                    itemList.append(feat[labelAttribute])
                    cb.addItem(feat[labelAttribute], unicode(feat[valueAttribute]))

            # Activate autocompletion
            completer = QCompleter(itemList, self)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setMaxVisibleItems(30)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            #~ completer.popup().setStyleSheet("background-color: lightblue")
            cb.setEditable(True)
            cb.setCompleter(completer)

        else:
            self.qc.updateLog(u'Veuillez charger des données cadastrales dans QGIS pour pouvoir effectuer une recherche')
            self.searchComboBoxes[combo]['layer'] = None
            self.searchComboBoxes[combo]['request'] = None
            self.searchComboBoxes[combo]['features'] = None
            self.searchComboBoxes[combo]['chosenFeature'] = None


    def setupCommuneCombobox(self):
        '''
        Create and fill a line edit with commune list
        And add autiocompletion
        '''
        self.setupSearchCombobox('commune')


    def setupSectionCombobox(self, filterAttribute=None, filterValue=None):
        '''
        Create and fill a line edit with section list
        And add autiocompletion
        '''
        self.setupSearchCombobox('section')


    def onSearchComboboxUpdate(self, combo):
        '''
        Update the combo box content
        '''

        # Get widget
        searchCombo = self.searchComboBoxes[combo]
        cb = searchCombo['widget']

        # Reinit
        self.searchComboBoxes[combo]['chosenFeature'] = None

        # Get chosen value
        searchValue = unicode(cb.currentText())
        searchColumn = searchCombo['valueAttribute']

        # Get corresponding feature and store it
        found = False
        if searchCombo['layer'] and searchCombo['features']:
            qe = QgsExpression('"%s" = \'%s\'' % (searchColumn, searchValue))
            for feat in searchCombo['layer'].getFeatures(searchCombo['request']):
                if qe.evaluate(feat):
                    # get geometry
                    self.searchComboBoxes[combo]['chosenFeature'] = feat
                    found = True

        #~ if found:
            #~ self.qc.updateLog(u'Trouvé pour %s et searchvalue %s' % (combo, searchValue))

    def onCommuneUpdate(self):
        '''
        Update the section combo box content
        depending on commune selected
        '''
        # Get commune feature and store it
        self.onSearchComboboxUpdate('commune')

        # update section combobox
        communeFeature = self.searchComboBoxes['commune']['chosenFeature']
        if communeFeature:
            filterExpression = "idu LIKE '" + communeFeature['idu'] + "%'"
            self.setupSearchCombobox('section', filterExpression)
        else:
            self.setupSearchCombobox('section')

    def onSectionUpdate(self):
        '''
        Update the section combo box content
        depending on section selected
        '''
        # Get commune feature and store it
        self.onSearchComboboxUpdate('section')



    def setZoomToChosenSearchCombobox(self, combo):
        '''
        Zoom to the item
        selected in Commune Section or Parcelle
        '''
        # Get widget
        searchCombo = self.searchComboBoxes[combo]
        cb = searchCombo['widget']

        # Zoom
        if searchCombo['chosenFeature']:
            geom = searchCombo['chosenFeature'].geometry()
            self.mc.setExtent(geom.boundingBox())
            self.mc.refresh()


    def setCenterToChosenSearchCombobox(self, combo):
        '''
        Center to the chosen commune
        in the combo box
        '''
        # Get widget
        searchCombo = self.searchComboBoxes[combo]
        cb = searchCombo['widget']

        # Center
        if searchCombo['chosenFeature']:
            # first get scale
            scale = self.mc.scale()
            # then zoom to geometry extent
            geom = searchCombo['chosenFeature'].geometry()
            self.mc.setExtent(geom.boundingBox())
            # the set the scale back
            self.mc.zoomScale(scale)
            self.mc.refresh()

    def setSelectionToChosenSearchCombobox(self, combo):
        '''
        Select the feature
        corresponding to the chosen commune
        '''
        # Get widget
        searchCombo = self.searchComboBoxes[combo]
        cb = searchCombo['widget']

        # Select
        if searchCombo['chosenFeature']:
            searchCombo['layer'].select(searchCombo['chosenFeature'].id())



    # COMMUNE

    def setZoomToChosenPlace(self):
        '''
        Zoom to the selected place
        in the combo box
        '''
        # Loop through 3 items and get the last
        w = None
        for key, item in self.searchComboBoxes.items():
            if item['chosenFeature']:
                w = key
        if w:
            self.setZoomToChosenSearchCombobox(w)

    def setCenterToChosenPlace(self):
        '''
        Center to the chosen place
        in the combo box
        '''
        # Loop through 3 items and get the last
        w = None
        for key, item in self.searchComboBoxes.items():
            if item['chosenFeature']:
                w = key
        if w:
            self.setCenterToChosenSearchCombobox(w)

    def setSelectionToChosenPlace(self):
        '''
        Select the feature
        corresponding to the chosen place
        '''
        # Loop through 3 items and get the last
        w = None
        for key, item in self.searchComboBoxes.items():
            if item['chosenFeature']:
                w = key
        if w:
            self.setSelectionToChosenSearchCombobox(w)



    def onVisibilityChange(self, visible):
        if visible:
            self.setupCommuneCombobox()
        else:
            self.txtLog.clear()



# --------------------------------------------------------
#        Interface - Let the user choose QGIS interface
# --------------------------------------------------------

from qadastre_interface_form import *

class qadastre_interface_dialog(QDialog, Ui_qadastre_interface_form):
    def __init__(self, iface):
        QDialog.__init__(self)
        self.iface = iface
        self.setupUi(self)

        # Signals/Slot Connections
        self.btInterfaceQadastre.clicked.connect(self.change_interface)


        # Set initial widget values

    def change_interface(self):
        onetext = unicode(self.lineEdit.text())
        qadastre_interface(self, onetext)



