import os

from tap_tester import connections, runner

from base import GoogleSearchConsoleBaseTest


class GoogleSearchConsoleStartDateTest(GoogleSearchConsoleBaseTest):

    start_date_1 = ""
    start_date_2 = ""

    @staticmethod
    def name():
        return "tap_tester_google_search_console_start_date_test"

    def test_run(self):
        """Instantiate start date according to the desired data set and run the test"""

        self.start_date_2 = self.get_properties().get('start_date')
        self.start_date_1 = self.timedelta_formatted(self.start_date_2, days=-1)

        start_date_1_epoch = self.dt_to_ts(self.start_date_1)
        start_date_2_epoch = self.dt_to_ts(self.start_date_2)

        self.start_date = self.start_date_1

        # Select fewer stream as tests take longer to complete
        expected_streams = ['sites', 'sitemaps', 'performance_report_date', 'performance_report_device']

        ##########################################################################
        ### First Sync
        ##########################################################################

        # instantiate connection
        conn_id_1 = connections.ensure_connection(self, original_properties=False)

        # run check mode
        found_catalogs_1 = self.run_and_verify_check_mode(conn_id_1)

        # table and field selection
        test_catalogs_1_all_fields = [catalog for catalog in found_catalogs_1
                                      if catalog.get('stream_name') in expected_streams]
        self.perform_and_verify_table_and_field_selection(conn_id_1, test_catalogs_1_all_fields, select_all_fields=True)

        # run initial sync
        record_count_by_stream_1 = self.run_and_verify_sync(conn_id_1)
        synced_records_1 = runner.get_records_from_target_output()

         ##########################################################################
        ### Update START DATE Between Syncs
        ##########################################################################

        print("REPLICATION START DATE CHANGE: {} ===>>> {} ".format(self.start_date, self.start_date_2))
        self.start_date = self.start_date_2

        ##########################################################################
        ### Second Sync
        ##########################################################################

        # create a new connection with the new start_date
        conn_id_2 = connections.ensure_connection(self, original_properties=False)

        # run check mode
        found_catalogs_2 = self.run_and_verify_check_mode(conn_id_2)

        # table and field selection
        test_catalogs_2_all_fields = [catalog for catalog in found_catalogs_2
                                      if catalog.get('stream_name') in expected_streams]
        self.perform_and_verify_table_and_field_selection(conn_id_2, test_catalogs_2_all_fields, select_all_fields=True)

        # run sync
        record_count_by_stream_2 = self.run_and_verify_sync(conn_id_2)
        synced_records_2 = runner.get_records_from_target_output()

        # Verify the total number of records replicated in sync 1 is greater than the number
        # of records replicated in sync 2
        self.assertGreater(sum(record_count_by_stream_1.values()), sum(record_count_by_stream_2.values()))

        for stream in expected_streams:

            with self.subTest(stream=stream):

                # expected values
                expected_primary_keys = self.expected_primary_keys()[stream]
                expected_bookmark_keys = self.expected_replication_keys()[stream]

                # collect information for assertions from syncs 1 & 2 base on expected values
                record_count_sync_1 = record_count_by_stream_1.get(stream, 0)
                record_count_sync_2 = record_count_by_stream_2.get(stream, 0)
                primary_keys_list_1 = [tuple(message.get('data').get(expected_pk) for expected_pk in expected_primary_keys)
                                       for message in synced_records_1.get(stream).get('messages')
                                       if message.get('action') == 'upsert']
                primary_keys_list_2 = [tuple(message.get('data').get(expected_pk) for expected_pk in expected_primary_keys)
                                       for message in synced_records_2.get(stream).get('messages')
                                       if message.get('action') == 'upsert']

                primary_keys_sync_1 = set(primary_keys_list_1)
                primary_keys_sync_2 = set(primary_keys_list_2)

                if self.is_incremental(stream):

                    bookmark_keys_list_1 = [message.get('data').get(next(iter(expected_bookmark_keys))) for message in synced_records_1.get(stream).get('messages')
                                            if message.get('action') == 'upsert']
                    bookmark_keys_list_2 = [message.get('data').get(next(iter(expected_bookmark_keys))) for message in synced_records_2.get(stream).get('messages')
                                            if message.get('action') == 'upsert']

                    bookmark_key_sync_1 = set(bookmark_keys_list_1)
                    bookmark_key_sync_2 = set(bookmark_keys_list_2)

                    # Verify bookmark key values are greater than or equal to start date of sync 1
                    for bookmark_key_value in bookmark_key_sync_1:
                        self.assertGreaterEqual(self.dt_to_ts(bookmark_key_value), start_date_1_epoch)

                    # Verify bookmark key values are greater than or equal to start date of sync 2
                    for bookmark_key_value in bookmark_key_sync_2:
                        self.assertGreaterEqual(self.dt_to_ts(bookmark_key_value), start_date_2_epoch)

                    # Verify the number of records replicated in sync 1 is greater than the number
                    # of records replicated in sync 2 for stream
                    self.assertGreater(record_count_sync_1, record_count_sync_2)

                    # Verify the records replicated in sync 2 were also replicated in sync 1
                    self.assertTrue(primary_keys_sync_2.issubset(primary_keys_sync_1))

                else:
                    
                    # Verify that the 2nd sync with a later start date replicates the same number of
                    # records as the 1st sync.
                    self.assertEqual(record_count_sync_2, record_count_sync_1)

                    # Verify by primary key the same records are replicated in the 1st and 2nd syncs
                    self.assertSetEqual(primary_keys_sync_1, primary_keys_sync_2)
