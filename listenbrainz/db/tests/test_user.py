# -*- coding: utf-8 -*-

import listenbrainz.db.user as db_user
import listenbrainz.db.spotify as db_spotify
import listenbrainz.db.stats as db_stats
import sqlalchemy
import time
import ujson

from listenbrainz import db
from listenbrainz.db.testing import DatabaseTestCase
from listenbrainz.db.model.user_artist_stat import UserArtistStatJson


class UserTestCase(DatabaseTestCase):
    def test_create(self):
        user_id = db_user.create(0, "izzy_cheezy")
        self.assertIsNotNone(db_user.get(user_id))

    def test_get_by_musicbrainz_row_id(self):
        user_id = db_user.create(0, 'frank')
        user = db_user.get_by_mb_row_id(0)
        self.assertEqual(user['id'], user_id)
        user = db_user.get_by_mb_row_id(0, musicbrainz_id='frank')
        self.assertEqual(user['id'], user_id)

    def test_update_token(self):
        user = db_user.get_or_create(1, 'testuserplsignore')
        old_token = user['auth_token']
        db_user.update_token(user['id'])
        user = db_user.get_by_mb_id('testuserplsignore')
        self.assertNotEqual(old_token, user['auth_token'])

    def test_update_last_login(self):
        """ Tests db.user.update_last_login """

        user = db_user.get_or_create(2, 'testlastloginuser')

        # set the last login value of the user to 0
        with db.engine.connect() as connection:
            connection.execute(sqlalchemy.text("""
                UPDATE "user"
                   SET last_login = to_timestamp(0)
                 WHERE id = :id
            """), {
                'id': user['id']
            })

        user = db_user.get(user['id'])
        self.assertEqual(int(user['last_login'].strftime('%s')), 0)

        db_user.update_last_login(user['musicbrainz_id'])
        user = db_user.get_by_mb_id(user['musicbrainz_id'])

        # after update_last_login, the val should be greater than the old value i.e 0
        self.assertGreater(int(user['last_login'].strftime('%s')), 0)

    def test_update_latest_import(self):
        user = db_user.get_or_create(3, 'updatelatestimportuser')
        self.assertEqual(int(user['latest_import'].strftime('%s')), 0)

        val = int(time.time())
        db_user.update_latest_import(user['musicbrainz_id'], val)
        user = db_user.get_by_mb_id(user['musicbrainz_id'])
        self.assertEqual(int(user['latest_import'].strftime('%s')), val)

    def test_increase_latest_import(self):
        user = db_user.get_or_create(4, 'testlatestimportuser')

        val = int(time.time())
        db_user.increase_latest_import(user['musicbrainz_id'], val)
        user = db_user.get_by_mb_id(user['musicbrainz_id'])
        self.assertEqual(val, int(user['latest_import'].strftime('%s')))

        db_user.increase_latest_import(user['musicbrainz_id'], val - 10)
        user = db_user.get_by_mb_id(user['musicbrainz_id'])
        self.assertEqual(val, int(user['latest_import'].strftime('%s')))

        val += 10
        db_user.increase_latest_import(user['musicbrainz_id'], val)
        user = db_user.get_by_mb_id(user['musicbrainz_id'])
        self.assertEqual(val, int(user['latest_import'].strftime('%s')))

    def test_reset_latest_import(self):
        user = db_user.get_or_create(7, 'resetlatestimportuser')
        self.assertEqual(int(user['latest_import'].strftime('%s')), 0)

        val = int(time.time())
        db_user.update_latest_import(user['musicbrainz_id'], val)
        user = db_user.get_by_mb_id(user['musicbrainz_id'])
        self.assertEqual(int(user['latest_import'].strftime('%s')), val)

        db_user.reset_latest_import(user['musicbrainz_id'])
        user = db_user.get_by_mb_id(user['musicbrainz_id'])
        self.assertEqual(int(user['latest_import'].strftime('%s')), 0)

    def test_get_all_users(self):
        """ Tests that get_all_users returns ALL users in the db """

        users = db_user.get_all_users()
        self.assertEqual(len(users), 0)
        db_user.create(8, 'user1')
        users = db_user.get_all_users()
        self.assertEqual(len(users), 1)
        db_user.create(9, 'user2')
        users = db_user.get_all_users()
        self.assertEqual(len(users), 2)

    def test_get_all_users_columns(self):
        """ Tests that get_all_users only returns those columns which are asked for """

        # check that all columns of the user table are present
        # if columns is not specified
        users = db_user.get_all_users()
        for user in users:
            for column in db_user.USER_GET_COLUMNS:
                self.assertIn(column, user)

        # check that only id is present if columns = ['id']
        users = db_user.get_all_users(columns=['id'])
        for user in users:
            self.assertIn('id', user)
            for column in db_user.USER_GET_COLUMNS:
                if column != 'id':
                    self.assertNotIn(column, user)

    def test_delete(self):
        user_id = db_user.create(10, 'frank')

        user = db_user.get(user_id)
        self.assertIsNotNone(user)

        with open(self.path_to_data_file('user_top_artists_db.json')) as f:
            artists_data = ujson.load(f)
        db_stats.insert_user_artists(
            user_id=user_id,
            artists=UserArtistStatJson(**{'all_time': artists_data}),
        )
        user_stats = db_stats.get_user_artists(user_id, 'all_time')
        self.assertIsNotNone(user_stats)

        db_user.delete(user_id)
        user = db_user.get(user_id)
        self.assertIsNone(user)
        user_stats = db_stats.get_user_artists(user_id, 'all_time')
        self.assertIsNone(user_stats)

    def test_delete_when_spotify_import_activated(self):
        user_id = db_user.create(11, 'kishore')
        user = db_user.get(user_id)
        self.assertIsNotNone(user)
        db_spotify.create_spotify(user_id, 'user token', 'refresh token', 0, True, 'user-read-recently-played')

        db_user.delete(user_id)
        user = db_user.get(user_id)
        self.assertIsNone(user)
        token = db_spotify.get_token_for_user(user_id)
        self.assertIsNone(token)

    def test_validate_usernames(self):
        db_user.create(11, 'eleven')
        db_user.create(12, 'twelve')

        users = db_user.validate_usernames([])
        self.assertListEqual(users, [])

        users = db_user.validate_usernames(['eleven', 'twelve'])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]['musicbrainz_id'], 'eleven')
        self.assertEqual(users[1]['musicbrainz_id'], 'twelve')

        users = db_user.validate_usernames(['twelve', 'eleven'])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]['musicbrainz_id'], 'twelve')
        self.assertEqual(users[1]['musicbrainz_id'], 'eleven')

        users = db_user.validate_usernames(['twelve', 'eleven', 'thirteen'])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]['musicbrainz_id'], 'twelve')
        self.assertEqual(users[1]['musicbrainz_id'], 'eleven')

    def test_get_users_in_order(self):
        id1 = db_user.create(11, 'eleven')
        id2 = db_user.create(12, 'twelve')

        users = db_user.get_users_in_order([])
        self.assertListEqual(users, [])

        users = db_user.get_users_in_order([id1, id2])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]['id'], id1)
        self.assertEqual(users[1]['id'], id2)

        users = db_user.get_users_in_order([id2, id1])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]['id'], id2)
        self.assertEqual(users[1]['id'], id1)

        users = db_user.get_users_in_order([id2, id1, 213213132])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]['id'], id2)
        self.assertEqual(users[1]['id'], id1)
